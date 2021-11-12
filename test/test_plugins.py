#!/usr/bin/env python
# -*- coding: UTF-8 -*-

# pylint: disable=protected-access,import-outside-toplevel

import importlib
import sys
import unittest
from inspect import getclosurevars
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

import yt_dlp

import ytdlp_plugins
from ytdlp_plugins import (
    OVERRIDDEN,
    PACKAGE_NAME,
    directories,
    initialize,
    load_plugins,
    patch_context,
    reset,
    add_plugins,
)

ROOT_DIR = Path(__file__).parents[1].absolute()

initialize()


class TestPlugins(unittest.TestCase):
    SAMPLE_PLUGIN_DIR = ROOT_DIR / PACKAGE_NAME

    def test_plugin_directory_structure(self):
        self.assertTrue(self.SAMPLE_PLUGIN_DIR.joinpath("__init__.py").exists())
        self.assertTrue(self.SAMPLE_PLUGIN_DIR.joinpath("extractor").is_dir())
        self.assertFalse(
            self.SAMPLE_PLUGIN_DIR.joinpath("extractor", "__init__.py").exists()
        )
        self.assertTrue(self.SAMPLE_PLUGIN_DIR.joinpath("postprocessor").is_dir())
        self.assertFalse(
            self.SAMPLE_PLUGIN_DIR.joinpath("postprocessor", "__init__.py").exists()
        )

    def test_directories_containing_plugins(self):
        plugin_dirs = {Path(path) for path in directories()}
        self.assertIn(self.SAMPLE_PLUGIN_DIR, plugin_dirs)

    def test_extractor_classes(self):
        plugins_ie = load_plugins("extractor", "IE")
        self.assertIn("ExamplePluginIE", plugins_ie.keys())

    def test_postprocessor_classes(self):
        plugins_pp = load_plugins("postprocessor", "PP")
        self.assertIn("ExamplePluginPP", plugins_pp.keys())

    def test_importing_zipped_module(self):
        """
        create a zip file with plugins and check if it can be imported
        """
        with TemporaryDirectory() as tmp:
            zipmodule_path = Path(tmp, "plugins.zip")
            with ZipFile(zipmodule_path, mode="w") as zipmodule:
                for file in self.SAMPLE_PLUGIN_DIR.rglob("*.py"):
                    zipmodule.write(
                        file, arcname=file.relative_to(self.SAMPLE_PLUGIN_DIR.parent)
                    )

            sys.path.append(str(zipmodule_path))  # add zip to search paths
            reset()
            add_plugins()

            for plugin_type in ("extractor", "postprocessor"):
                package = importlib.import_module(f"{PACKAGE_NAME}.{plugin_type}")
                self.assertIn(
                    zipmodule_path / PACKAGE_NAME / plugin_type,
                    map(Path, package.__path__),
                )

    def test_overridden_classes(self):
        reset()
        add_plugins()

        overridden_names = {cls.__name__ for cls in OVERRIDDEN}
        self.assertGreaterEqual(len(overridden_names), 2)
        all_names = set(yt_dlp.extractor.__dict__.keys()) | set(
            yt_dlp.postprocessor.__dict__.keys()
        )

        not_in_names = ", ".join(overridden_names - all_names)
        self.assertFalse(not_in_names, f"missing {not_in_names} in extractor namespace")

        all_classes = getattr(yt_dlp.extractor, "_ALL_CLASSES", ())
        for cls in OVERRIDDEN:
            self.assertFalse(
                cls in all_classes,
                f"Overridden class {cls.__name__!r} still found in _ALL_CLASSES",
            )

    @staticmethod
    def _path(_func):
        return f"{_func.__module__}.{_func.__name__}"

    def test_patched_json_writer(self):
        patched_func = ytdlp_plugins.write_json_file
        function_name = patched_func.__name__
        with patch_context():
            _nonlocals, _globals, _builtins, _unbound = getclosurevars(
                yt_dlp.YoutubeDL._write_info_json
            )
            self.assertIn(function_name, _globals)
            used_func = _globals[function_name]
        self.assertIs(
            used_func,
            patched_func,
            f"class {self._path(yt_dlp.YoutubeDL)!r} still uses function {self._path(used_func)!r}",
        )

    def test_unpatched_json_writer(self):
        from yt_dlp.utils import write_json_file as orig_func

        function_name = orig_func.__name__
        _nonlocals, _globals, _builtins, _unbound = getclosurevars(
            yt_dlp.YoutubeDL._write_info_json
        )
        self.assertIn(function_name, _globals)
        used_func = _globals[function_name]
        self.assertIs(
            used_func,
            orig_func,
            f"class {self._path(yt_dlp.YoutubeDL._write_info_json)!r} "
            f"uses unexpected function {self._path(used_func)!r}",
        )

    def test_patched_bug_report_message(self):
        orig_bug_report = yt_dlp.utils.bug_reports_message()
        self.assertIn("yt-dlp", orig_bug_report)

        params = dict(skip_download=True)
        ydl = yt_dlp.YoutubeDL(params, auto_init=True)
        with self.assertRaises(yt_dlp.utils.DownloadError) as context:
            with patch_context():
                ydl.download(["failingplugin:hello"])

        exc, obj, _ = context.exception.exc_info
        self.assertEqual(orig_bug_report, yt_dlp.utils.bug_reports_message())
        self.assertIs(exc, yt_dlp.utils.ExtractorError)
        self.assertNotIn(
            orig_bug_report,
            str(obj),
            "Bug report message is not suppressed",
        )

    def test_orig_bug_report_message(self):
        orig_bug_report = yt_dlp.utils.bug_reports_message()
        self.assertIn("yt-dlp", orig_bug_report)

        params = dict(skip_download=True)
        ydl = yt_dlp.YoutubeDL(params, auto_init=True)
        with self.assertRaises(yt_dlp.utils.DownloadError) as context:
            with patch_context():
                ydl.download(["http://www.vimeo.com/123/123"])

        exc, obj, _ = context.exception.exc_info
        self.assertEqual(orig_bug_report, yt_dlp.utils.bug_reports_message())
        self.assertIs(exc, yt_dlp.utils.ExtractorError)
        self.assertIn(
            orig_bug_report,
            str(obj),
            "Bug report message is not suppressed",
        )


if __name__ == "__main__":
    unittest.main()

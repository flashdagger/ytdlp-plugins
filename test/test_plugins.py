#!/usr/bin/env python
# -*- coding: UTF-8 -*-

# pylint: disable=protected-access,import-outside-toplevel

import importlib
import sys
import unittest
from contextlib import redirect_stderr
from inspect import getclosurevars
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.error import HTTPError
from zipfile import ZipFile

import yt_dlp

from ytdlp_plugins import (
    GLOBALS,
    PACKAGE_NAME,
    add_plugins,
    directories,
    load_plugins,
    utils,
)
from ytdlp_plugins.patching import patch_function_globals, SKIP_VT_MODE, patch_context

ROOT_DIR = Path(__file__).parents[1].absolute()

GLOBALS.initialize()


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
        for module_name in tuple(sys.modules):
            if module_name.startswith("ytdlp_plugins.extractor"):
                del sys.modules[module_name]
        plugins_ie = load_plugins(f"{PACKAGE_NAME}.extractor", "IE")
        self.assertIn("ytdlp_plugins.extractor.example", sys.modules.keys())
        self.assertIn("ExamplePluginIE", plugins_ie.keys())
        # don't load modules with underscore prefix
        self.assertFalse(
            "ytdlp_plugins.extractor._ignore" in sys.modules.keys(),
            "loaded module beginning with underscore",
        )

    def test_postprocessor_classes(self):
        plugins_pp = load_plugins(f"{PACKAGE_NAME}.postprocessor", "PP")
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
            GLOBALS.reset()
            add_plugins()

            for plugin_type in ("extractor", "postprocessor"):
                package = importlib.import_module(f"{PACKAGE_NAME}.{plugin_type}")
                self.assertIn(
                    zipmodule_path / PACKAGE_NAME / plugin_type,
                    map(Path, package.__path__),
                )

    def test_overridden_classes(self):
        GLOBALS.reset()
        add_plugins()

        overridden_names = set(GLOBALS.OVERRIDDEN.keys())
        self.assertGreaterEqual(len(overridden_names), 2)
        all_names = set(yt_dlp.extractor.__dict__.keys()) | set(
            yt_dlp.postprocessor.__dict__.keys()
        )

        not_in_names = ", ".join(overridden_names - all_names)
        self.assertFalse(not_in_names, f"missing {not_in_names} in extractor namespace")

        all_classes = getattr(yt_dlp.extractor, "_ALL_CLASSES", ())
        for cls in GLOBALS.OVERRIDDEN.values():
            self.assertFalse(
                cls in all_classes,
                f"Overridden class {cls.__name__!r} still found in _ALL_CLASSES",
            )

    @staticmethod
    def _path(_func):
        return f"{_func.__module__}.{_func.__name__}"

    def test_patched_json_writer(self):
        patched_func = utils.write_json_file
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
            f"class {self._path(yt_dlp.YoutubeDL)!r} uses "
            f"unpatched function {self._path(used_func)!r}",
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

    @SKIP_VT_MODE
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
            orig_bug_report, str(obj), "Bug report message is not suppressed"
        )

    @SKIP_VT_MODE
    def test_orig_bug_report_message(self):
        orig_bug_report = yt_dlp.utils.bug_reports_message()
        self.assertIn("yt-dlp", orig_bug_report)
        stderr = StringIO()

        with self.assertRaises(yt_dlp.utils.DownloadError) as context:
            with redirect_stderr(stderr):
                params = dict(skip_download=True)
                ydl = yt_dlp.YoutubeDL(params, auto_init=True)
                with patch_context():
                    ydl.download(["http://www.vimeo.com/123/123"])

        exc, obj, _ = context.exception.exc_info
        self.assertEqual(orig_bug_report, yt_dlp.utils.bug_reports_message())
        self.assertIn(exc, {HTTPError, yt_dlp.utils.ExtractorError})
        self.assertIn(
            orig_bug_report,
            stderr.getvalue(),
            "Original Bug report message is suppressed",
        )

    def test_patch_function_globals_warning(self):
        global_name = "_undefined"
        with self.assertWarnsRegex(RuntimeWarning, repr(global_name)):
            with patch_function_globals(self._path, None, global_name=global_name):
                pass


if __name__ == "__main__":
    unittest.main()

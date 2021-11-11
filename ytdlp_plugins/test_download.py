#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import json
import os
import re
import socket
from contextlib import suppress
from itertools import groupby, count
from math import log10
from operator import itemgetter
from pathlib import Path
from typing import Dict, Any, Callable, Optional, Tuple
from unittest import skipIf

import yt_dlp.YoutubeDL
from yt_dlp.compat import (
    compat_http_client,
    compat_urllib_error,
    compat_HTTPError,
)
from yt_dlp.extractor import get_info_extractor
from yt_dlp.utils import (
    DownloadError,
    ExtractorError,
    format_bytes,
    UnavailableVideoError,
)

from . import patch_context
from ._helper import (
    expect_warnings,
    get_params,
    get_testcases,
    md5,
    DownloadTestcase,
)
from .ast_utils import get_test_lineno

RETRIES = 3
with patch_context():
    YoutubeDLSuper = yt_dlp.YoutubeDL


class YoutubeDL(YoutubeDLSuper):
    def __init__(self, *args, **kwargs):
        self.to_stderr = self.to_screen
        self.processed_info_dicts = []
        super().__init__(*args, **kwargs)

    def report_warning(self, message, _only_once=False):
        # Don't accept warnings during tests
        raise ExtractorError(message)

    def process_info(self, info_dict):
        self.processed_info_dicts.append(info_dict)
        return super().process_info(info_dict)


class TestDownload(DownloadTestcase):
    # Parallel testing in nosetests. See
    # http://nose.readthedocs.org/en/latest/doc_tests/test_multiprocess/multiprocess.html
    _multiprocess_shared_ = True
    maxDiff = None
    test_case: Dict[str, Any] = {}

    def __str__(self):
        """Identify each test with the `add_ie` attribute, if available."""

        def strclass(cls):
            return f"{cls.__module__}.{cls.__name__}"

        add_ie = self.test_case.get("add_ie", [])
        add_ie_str = f" [{','.join(add_ie)}]" if add_ie else ""
        return f"{self._testMethodName} ({strclass(self.__class__)}){add_ie_str}:"

    def setUp(self):
        self.finished_hook_called = set()
        self.ydl = YoutubeDL(auto_init=False)
        self.params: Dict[str, Any] = {}

    def get_tc_filename(self, test_case) -> Path:
        return Path(self.ydl.prepare_filename(dict(test_case.get("info_dict", {}))))

    def try_rm_tcs_files(self, *test_cases: Dict[str, Any]) -> None:
        def unlink_if_exist(path: Path):
            with suppress(FileNotFoundError):
                path.unlink()

        for test_case in test_cases:
            tc_filename = self.get_tc_filename(test_case)
            self.assertFalse(tc_filename.is_dir())
            unlink_if_exist(tc_filename)
            unlink_if_exist(tc_filename.with_name(tc_filename.name + ".part"))
            unlink_if_exist(tc_filename.with_suffix(".info.json"))

    def get_info_dict(self, test_case):
        tc_filename = self.get_tc_filename(test_case).with_suffix(".info.json")
        self.assertTrue(tc_filename.exists(), f"Missing info file {tc_filename}")
        info_dict = json.loads(tc_filename.read_text(encoding="utf-8"))
        return info_dict

    def _hook(self, status):
        if status["status"] == "finished":
            self.finished_hook_called.add(Path(status["filename"]))

    @staticmethod
    def is_playlist(test_case):
        return any(k.startswith("playlist") for k in test_case)

    def check_playlist(self, res_dict):
        self.assertTrue(res_dict["_type"] in {"playlist", "multi_video"})
        self.assertTrue("entries" in res_dict)

        if "playlist_mincount" in self.test_case:
            self.assertGreaterEqual(
                len(res_dict["entries"]),
                self.test_case["playlist_mincount"],
                f"Expected at least {self.test_case['playlist_mincount']:d} "
                f"according to field playlist_mincount, "
                f"but got only {len(res_dict['entries']):d}",
            )
        if "playlist_count" in self.test_case:
            self.assertEqual(
                len(res_dict["entries"]),
                self.test_case["playlist_count"],
                f"Expected {self.test_case['playlist_count']:d} entries "
                f"according to field playlist_count, "
                f"but got {len(res_dict['entries']):d}.",
            )
        if "playlist_duration_sum" in self.test_case:
            got_duration = sum(e["duration"] for e in res_dict["entries"])
            self.expect_value(
                got_duration,
                self.test_case["playlist_duration_sum"],
                "playlist_duration_sum",
            )

    def precheck_testcase(self, test_case):
        info_dict = test_case.get("info_dict", {})
        if not info_dict.get("id"):
            raise Exception("Test definition incorrect. 'id' key is not present")

        if not (self.is_playlist(test_case) or info_dict.get("ext")):
            if self.params.get("skip_download") and self.params.get(
                "ignore_no_formats_error"
            ):
                return

            raise Exception(
                "Test definition incorrect. "
                "The output file cannot be known. 'ext' key is not present"
            )

    def initialize(self, test_case, test_name) -> None:
        params = get_params(test_case.get("params", {}))
        params["outtmpl"] = test_name + "_" + params["outtmpl"]
        if self.is_playlist(test_case) and "playlist" not in test_case:
            params.setdefault("extract_flat", "in_playlist")
            params.setdefault("playlistend", test_case.get("playlist_mincount"))
            params.setdefault("skip_download", True)

        self.params.update(params)
        self.ydl = YoutubeDL(params, auto_init=False)
        self.ydl.add_default_info_extractors()
        self.ydl.add_progress_hook(self._hook)
        expect_warnings(self.ydl, test_case.get("expected_warnings", []))

    def extract_info(self) -> Optional[Dict[str, Any]]:
        try:
            # We're not using .download here since that is just a shim
            # for outside error handling, and returns the exit code
            # instead of the result dict.
            return self.ydl.extract_info(
                self.test_case["url"],
                force_generic_extractor=self.ydl.params.get(
                    "force_generic_extractor", False
                ),
            )
        except (DownloadError, ExtractorError) as err:
            # Check if the exception is not a network related one
            if (
                not err.exc_info[0]
                in (
                    compat_urllib_error.URLError,
                    socket.timeout,
                    UnavailableVideoError,
                    compat_http_client.BadStatusLine,
                )
                or (err.exc_info[0] == compat_HTTPError and err.exc_info[1].code == 503)
            ):
                raise

        return None

    def check_testcase(self, test_case):
        info_dict = self.get_info_dict(test_case)
        tc_filename = self.get_tc_filename(test_case)

        if not (self.is_playlist(test_case) or self.params.get("skip_download", False)):
            self.assertTrue(tc_filename.exists(), msg=f"Missing file {tc_filename}")
            self.assertTrue(
                tc_filename in self.finished_hook_called,
                (tc_filename, self.finished_hook_called),
            )
            expected_minsize = test_case.get("file_minsize", 10000)
            if expected_minsize is not None:
                if self.ydl.params.get("test"):
                    expected_minsize = max(expected_minsize, 10000)
                got_fsize = os.path.getsize(tc_filename)
                self.assertGreaterEqual(
                    got_fsize,
                    expected_minsize,
                    f"Expected {tc_filename} to be at least "
                    f"{format_bytes(expected_minsize)}, "
                    f"but it's only {format_bytes(got_fsize)} ",
                )
            if "md5" in test_case:
                self.expect_value(md5(tc_filename), test_case["md5"], "md5")
        # Finally, check test cases' data again but this time against
        # extracted data from info JSON file written during processing
        self.expect_info_dict(info_dict, test_case.get("info_dict", {}))


# Dynamically generate tests
def generator(test_case, test_name: str, test_index: int) -> Callable:
    def skip_reason() -> Tuple[bool, str]:
        if "skip" in test_case:
            return True, test_case["skip"]

        if not test_case["cls"]().working():
            return True, "IE marked as not _WORKING"

        other_ies = [
            get_info_extractor(ie_key)() for ie_key in test_case.get("add_ie", [])
        ]
        for other_ie in other_ies:
            if not other_ie.working():
                return (
                    True,
                    f"test depends on {other_ie.ie_key()}IE, marked as not WORKING",
                )

        return False, ""

    def raise_with_test_location(exc, playlist_idx: Optional[int] = None):
        msg = str(exc).split(" : ", maxsplit=1)[-1]
        info = get_test_lineno(test_case["cls"], index=test_index)
        filename = info["_file"]
        with suppress(TypeError, IndexError, KeyError):
            info = info["playlist"][playlist_idx]
        line_no = info["_lineno"].get("info_dict") or info["_lineno"]["_self"]

        match = re.match(r".*\bfield (\w+)", msg)
        with suppress(KeyError, AttributeError):
            line_no = info["_lineno"][match.group(1)]
        with suppress(KeyError, AttributeError):
            line_no = info["info_dict"]["_lineno"][match.group(1)]
        # print(f"\n{filename}:{line_no}: {msg}", file=sys.stderr)
        code_obj = compile(
            "raise type(exc)(msg) from exc",
            "",
            "exec",
        )
        #  pylint: disable=exec-used
        exec(
            code_obj.replace(
                co_firstlineno=line_no,
                co_name=test_name,
                co_filename=filename,
            )
        )

    def test_url(self):
        try:
            _cls = test_case["cls"]
            self.assertTrue(
                _cls.suitable(test_case["url"]), "field url does not match extractor"
            )
        except AssertionError as exc:
            raise_with_test_location(exc)

    def test_download(self):
        try:
            self.precheck_testcase(test_case)
            sub_test_cases = test_case.get("playlist", ())
            self.try_rm_tcs_files(test_case, *sub_test_cases)
            self.initialize(test_case, test_name)
            uut_dict = self.extract_info()
            self.expect_info_dict(uut_dict, test_case.get("info_dict", {}))
            if self.is_playlist(test_case):
                self.check_playlist(uut_dict)
            self.check_testcase(test_case)
        except AssertionError as exc:
            raise_with_test_location(exc)
            raise

        entries = uut_dict.get("entries", ())
        for idx, sub_test_case, sub_uut_dict in zip(count(), sub_test_cases, entries):
            with self.subTest(
                "playlist entry",
                id=sub_test_case.get("info_dict", {}).get("id", f"<{idx}>"),
            ):
                try:
                    self.precheck_testcase(sub_test_case)
                    # First, check test cases' data against extracted data alone
                    self.expect_info_dict(
                        sub_uut_dict, sub_test_case.get("info_dict", {})
                    )
                    self.check_testcase(sub_test_case)
                    self.try_rm_tcs_files(sub_test_case)
                except AssertionError as exc:
                    raise_with_test_location(exc, playlist_idx=idx)
                    raise

        self.try_rm_tcs_files(test_case)
        test_ids = {
            _test_case.get("info_dict", {}).get("id") for _test_case in sub_test_cases
        }
        residue_testcases = [
            {"info_dict": entry} for entry in entries if entry.get("id") not in test_ids
        ]
        self.try_rm_tcs_files(*residue_testcases)

    test_func = skipIf(*skip_reason())(
        test_url if test_case.get("only_matching", False) else test_download
    )
    cls = type(
        f"Test{test_name}",
        (TestDownload,),
        {"test_case": test_case, test_func.__name__: test_func},
    )
    return cls


def main():
    for name, test_case_it in groupby(get_testcases(), itemgetter("name")):
        test_cases = tuple(test_case_it)
        num_tcs = len(test_cases)
        width = int(log10(num_tcs)) + 1
        for idx, test_case in enumerate(test_cases):
            test_name = f"{name}_{idx + 1:0{width}}" if num_tcs > 1 else name
            cls = generator(test_case, test_name, idx)
            cls.__module__ = test_case.get("cls", cls).__module__
            globals()[cls.__name__] = cls


main()

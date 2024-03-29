#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import json
import os
import re
import sys
from contextlib import suppress
from functools import reduce
from http.client import BadStatusLine
from itertools import count, groupby
from math import log10
from operator import getitem, itemgetter
from pathlib import Path
from types import CodeType
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from unittest import skipIf
from urllib.error import HTTPError

import yt_dlp.extractor
from yt_dlp.utils import (
    DownloadError,
    ExtractorError,
    UnavailableVideoError,
    format_bytes,
)

from ._helper import DownloadTestcase, expect_warnings, get_params, get_testcases
from .ast_utils import get_test_lineno
from .patching import SKIP_VT_MODE, patch_decorator
from .utils import md5

InfoDict = Dict[str, Any]
EXC_CODE_STR = "raise exc_cls(msg) from exc"
EXC_CODE_OBJ = compile(EXC_CODE_STR, "", "exec")
FILE_ERRORS = (
    (FileNotFoundError, WindowsError) if os.name == "nt" else (FileNotFoundError,)
)


class YoutubeDL(yt_dlp.YoutubeDL):
    @SKIP_VT_MODE
    def __init__(self, *args, **kwargs):
        self.to_stderr = self.to_screen
        super().__init__(*args, **kwargs)

    def report_warning(self, message: str, _only_once=False):
        # Don't accept warnings during tests
        raise ExtractorError(message)


# pylint: disable=too-few-public-methods
class ExtractorTestData:
    __slots__ = (
        "test_case",
        "sub_test_cases",
        "is_playlist",
        "params",
        "finished_hook_called",
        "ydl",
    )

    def __init__(self, test_case: InfoDict, test_name: str) -> None:
        self.test_case = test_case
        self.is_playlist = any(k.startswith("playlist") for k in test_case)
        self.sub_test_cases: List[InfoDict] = test_case.get("playlist", ())
        self.finished_hook_called: Set[Path] = set()

        params = get_params(override=test_case.get("params"))
        params["outtmpl"] = test_name + "_" + params["outtmpl"]
        if self.is_playlist and "playlist" not in test_case:
            params.setdefault("extract_flat", "in_playlist")
            params.setdefault("playlistend", test_case.get("playlist_mincount"))
            params.setdefault("skip_download", True)

        self.params = params
        self.ydl = YoutubeDL(params, auto_init=False)

        self.ydl.add_default_info_extractors()
        self.ydl.add_progress_hook(self.status_hook)
        expect_warnings(self.ydl, test_case.get("expected_warnings", []))

    def status_hook(self, status: InfoDict) -> None:
        if status["status"] == "finished":
            self.finished_hook_called.add(Path(status["filename"]))


class TestExtractor(DownloadTestcase):
    maxDiff = None
    _data: Dict["TestExtractor", ExtractorTestData] = {}

    def __str__(self):
        """Identify each test with the `add_ie` attribute, if available."""
        return f"{self.__class__.__name__}::{self._testMethodName}"

    @property
    def data(self) -> ExtractorTestData:
        return self._data[self]

    def initialize(self, test_case: InfoDict, test_name: str):
        self._data[self] = ExtractorTestData(test_case, test_name)

    def get_tc_filename(self, test_case: InfoDict) -> Path:
        info = dict(test_case.get("info_dict", {}))
        info["duration"] = None  # fails if duration is 'int'
        return Path(self.data.ydl.prepare_filename(info))

    def try_rm_tcs_files(self, *test_cases: InfoDict) -> None:
        if not test_cases:
            test_cases = tuple((self.data.test_case, *self.data.sub_test_cases))

        def unlink_if_exist(path: Path):
            with suppress(*FILE_ERRORS):
                path.unlink()

        for test_case in test_cases:
            tc_filename = self.get_tc_filename(test_case)
            self.assertFalse(tc_filename.is_dir())
            unlink_if_exist(tc_filename)
            unlink_if_exist(tc_filename.with_name(tc_filename.name + ".part"))
            unlink_if_exist(tc_filename.with_suffix(".info.json"))

    def get_info_dict(self, test_case: InfoDict) -> InfoDict:
        tc_filename = self.get_tc_filename(test_case).with_suffix(".info.json")
        self.assertTrue(tc_filename.exists(), f"Missing info file {tc_filename}")
        info_dict = json.loads(tc_filename.read_text(encoding="utf-8"))
        return info_dict

    def check_playlist(self, res_dict: InfoDict) -> None:
        if not self.data.is_playlist:
            return

        self.assertTrue(res_dict["_type"] in {"playlist", "multi_video"})
        self.assertTrue("entries" in res_dict)

        if "playlist_mincount" in self.data.test_case:
            self.assertGreaterEqual(
                len(res_dict["entries"]),
                self.data.test_case["playlist_mincount"],
                f"Expected at least {self.data.test_case['playlist_mincount']:d} "
                f"according to field playlist_mincount, "
                f"but got only {len(res_dict['entries']):d}",
            )
        if "playlist_count" in self.data.test_case:
            self.assertEqual(
                len(res_dict["entries"]),
                self.data.test_case["playlist_count"],
                f"Expected {self.data.test_case['playlist_count']:d} entries "
                f"according to field playlist_count, "
                f"but got {len(res_dict['entries']):d}.",
            )
        if "playlist_duration_sum" in self.data.test_case:
            got_duration = sum(e["duration"] for e in res_dict["entries"])
            self.expect_value(
                got_duration,
                self.data.test_case["playlist_duration_sum"],
                "playlist_duration_sum",
            )

    def check_fields(self, test_case: InfoDict) -> None:
        info_dict = test_case.get("info_dict", {})
        self.assert_field_is_present(info_dict, "id")

        params = test_case.get("params", {})
        expr = (
            self.data.is_playlist
            or info_dict.get("ext")
            or (params.get("skip_download") and params.get("ignore_no_formats_error"))
        )
        self.assert_field_is_present(expr, "ext")

    def extract_info(self) -> Optional[InfoDict]:
        try:
            # We're not using .download here since that is just a shim
            # for outside error handling, and returns the exit code
            # instead of the result dict.
            return self.data.ydl.extract_info(
                self.data.test_case["url"],
                force_generic_extractor=self.data.ydl.params.get(
                    "force_generic_extractor", False
                ),
            )
        except (DownloadError, ExtractorError) as err:
            # Check if the exception is not a network related one
            if not err.exc_info[0] in (
                # URLError,
                # socket.timeout,
                UnavailableVideoError,
                BadStatusLine,
            ) or (err.exc_info[0] == HTTPError and err.exc_info[1].code == 503):
                raise

        return None

    def check_testcase(self, test_case: InfoDict, is_playlist=False) -> None:
        info_dict = self.get_info_dict(test_case)
        tc_filename = self.get_tc_filename(test_case)

        if not (is_playlist or self.data.params.get("skip_download", False)):
            self.assertTrue(tc_filename.exists(), msg=f"Missing file {tc_filename}")
            no_merge = "+" not in info_dict["format_id"]
            if no_merge:
                self.assertTrue(
                    tc_filename in self.data.finished_hook_called,
                    f"finished hook not called for expected file {tc_filename!s}",
                )
            expected_minsize = test_case.get("file_minsize", 10000)
            if expected_minsize:
                if self.data.ydl.params.get("test"):
                    expected_minsize = max(expected_minsize, 10000)
                got_fsize = os.path.getsize(tc_filename)
                self.assert_field_is_valid(
                    got_fsize >= expected_minsize,
                    "file_minsize",
                    f"Expected {tc_filename} to be at least "
                    f"{format_bytes(expected_minsize)}, "
                    f"but it's only {format_bytes(got_fsize)} ",
                )
            if "md5" in test_case:
                self.expect_value(md5(tc_filename), test_case["md5"], "md5")
        # Finally, check test cases' data again but this time against
        # extracted data from info JSON file written during processing
        self.expect_info_dict(info_dict, test_case.get("info_dict", {}))

    def raise_with_test_location(
        self, test_name: str, test_index: int, playlist_idx: Optional[int] = None
    ) -> None:
        _exc_type, exc, _tb = sys.exc_info()
        msg = str(exc)
        parts = msg.split(" : ", maxsplit=1)
        if " field " not in parts[0]:
            msg = parts[-1]
        info = get_test_lineno(self.data.test_case["cls"], index=test_index)
        filename = info["_file"]
        with suppress(TypeError, IndexError, KeyError):
            info = info["playlist"][playlist_idx]

        match = re.match(r".*\bfield ['\"]?(\w+)", msg)
        for path in (
            ("info_dict", "_lineno", match and match[1]),
            ("_lineno", match and match[1]),
            ("_lineno", "info_dict"),
            ("_lineno", "_self"),
        ):
            with suppress(KeyError, IndexError):
                line_no: int = reduce(getitem, path, info)  # type: ignore
                break
        else:
            line_no = 1

        exc_cls = type(test_name, (type(exc),), {})
        # pylint: disable=exec-used
        exec(
            exc_code_obj(
                co_firstlineno=line_no, co_name=test_name, co_filename=filename
            ),
            {"exc": exc, "exc_cls": exc_cls, "msg": msg},
        )


def exc_code_obj(co_firstlineno: int, co_name: str, co_filename: str) -> CodeType:
    if hasattr(EXC_CODE_OBJ, "replace"):
        return EXC_CODE_OBJ.replace(
            co_name=co_name, co_filename=co_filename, co_firstlineno=co_firstlineno
        )
    return compile("\n" * (co_firstlineno - 1) + EXC_CODE_STR, co_filename, "exec")


# Dynamically generate tests
def generator(test_case, test_name: str, test_index: int) -> Tuple[str, Callable]:
    def skip_reason() -> Tuple[bool, str]:
        if "skip" in test_case:
            return True, str(test_case["skip"])

        if not getattr(test_case["cls"], "_WORKING", False):
            return True, "_WORKING=False"

        ie_map = {
            ie_key: getattr(yt_dlp.extractor, f"{ie_key}IE", None)
            for ie_key in test_case.get("add_ie", ())
        }
        missing_ies = [ie_key for ie_key, ie_cls in ie_map.items() if ie_cls is None]
        if missing_ies:
            return (
                True,
                f"depends on {', '.join(missing_ies)} - which don't exist",
            )

        ie_not_working = [
            ie_key
            for ie_key, ie_cls in ie_map.items()
            if ie_cls and not getattr(ie_cls, "_WORKING", False)
        ]
        if ie_not_working:
            return (
                True,
                f"depends on {', '.join(ie_not_working)} -  marked as not WORKING",
            )

        return False, ""

    def test_url(self: TestExtractor) -> None:
        try:
            self.assert_field_is_present(test_case, "url")
            self.assertTrue(
                test_case["cls"].suitable(test_case["url"]),
                "field url does not match extractor",
            )
        except AssertionError:
            self.raise_with_test_location(test_name, test_index)

    @patch_decorator
    def test_download(self: TestExtractor) -> None:
        self.initialize(test_case, test_name)
        try:
            self.assert_field_is_present(test_case, "url")
            self.check_fields(test_case)
            self.try_rm_tcs_files()
            uut_dict = self.extract_info() or {}
            self.expect_info_dict(uut_dict, test_case.get("info_dict", {}))
            self.check_playlist(uut_dict)
            self.check_testcase(test_case, is_playlist=self.data.is_playlist)
        except (AssertionError, DownloadError):
            self.raise_with_test_location(test_name, test_index)
            raise

        entries = uut_dict.get("entries", ())
        for idx, sub_test_case, sub_uut_dict in zip(
            count(), self.data.sub_test_cases, entries
        ):
            with self.subTest(
                "playlist entry",
                id=sub_test_case.get("info_dict", {}).get("id", f"<{idx}>"),
            ):
                try:
                    self.check_fields(sub_test_case)
                    # First, check test cases' data against extracted data alone
                    self.expect_info_dict(
                        sub_uut_dict, sub_test_case.get("info_dict", {})
                    )
                    self.check_testcase(sub_test_case)
                    self.try_rm_tcs_files(sub_test_case)
                except AssertionError:
                    self.raise_with_test_location(
                        test_name, test_index, playlist_idx=idx
                    )
                    raise

        test_ids = {
            _test_case.get("info_dict", {}).get("id")
            for _test_case in self.data.sub_test_cases
        }
        residue_testcases = [
            {"info_dict": entry} for entry in entries if entry.get("id") not in test_ids
        ]
        self.try_rm_tcs_files(test_case, *residue_testcases)

    test_func = skipIf(*skip_reason())(
        test_url if test_case.get("only_matching", False) else test_download
    )
    name = f"{test_func.__name__}_{test_name}".replace("_download_", "_")
    return name, test_func


def main():
    for name, test_case_it in groupby(get_testcases(), itemgetter("name")):
        test_cases = tuple(test_case_it)
        num_tcs = len(test_cases)
        width = int(log10(num_tcs)) + 1
        for idx, test_case in enumerate(test_cases):
            test_name = f"{name}_{idx + 1:0{width}}" if num_tcs > 1 else name
            func_name, func = generator(test_case, test_name, idx)
            setattr(TestExtractor, func_name, func)


main()

#!/usr/bin/env python
# -*- coding: UTF-8 -*-

import hashlib
import json
import os
import socket
from pathlib import Path
from typing import Optional, Sequence

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

from ._helper import (
    expect_warnings,
    get_params,
    gettestcases,
    report_warning,
    DownloadTestcase,
)

RETRIES = 3


class YoutubeDL(yt_dlp.YoutubeDL):
    def __init__(self, *args, **kwargs):
        self.to_stderr = self.to_screen
        self.processed_info_dicts = []
        super(YoutubeDL, self).__init__(*args, **kwargs)

    def report_warning(self, message, _only_once=False):
        # Don't accept warnings during tests
        raise ExtractorError(message)

    def process_info(self, info_dict):
        self.processed_info_dicts.append(info_dict)
        return super(YoutubeDL, self).process_info(info_dict)


def _file_md5(fn: Path) -> str:
    with fn.open("rb") as f:
        return hashlib.md5(f.read()).hexdigest()


defs = gettestcases()


class TestDownload(DownloadTestcase):
    # Parallel testing in nosetests. See
    # http://nose.readthedocs.org/en/latest/doc_tests/test_multiprocess/multiprocess.html
    _multiprocess_shared_ = True

    maxDiff = None

    COMPLETED_TESTS = {}

    def __str__(self):
        """Identify each test with the `add_ie` attribute, if available."""

        def strclass(cls):
            return f"{cls.__module__}.{cls.__name__}"

        add_ie = getattr(self, self._testMethodName).add_ie
        add_ie_str = f" [{add_ie}]" if add_ie else ""
        return f"{self._testMethodName} ({strclass(self.__class__)}){add_ie_str}:"

    def setUp(self):
        self.defs = defs


# Dynamically generate tests
def generator(test_case, tname):
    def test_template(self):
        if self.COMPLETED_TESTS.get(tname):
            return
        self.COMPLETED_TESTS[tname] = True
        ie = yt_dlp.extractor.get_info_extractor(test_case["name"])()
        other_ies = [
            get_info_extractor(ie_key)() for ie_key in test_case.get("add_ie", [])
        ]
        is_playlist = any(k.startswith("playlist") for k in test_case)
        test_cases = test_case.get("playlist", [] if is_playlist else [test_case])

        def print_skipping(reason):
            print(f"Skipping {test_case['name']}: {reason}")

        if not ie.working():
            print_skipping("IE marked as not _WORKING")
            return

        for tc in test_cases:
            info_dict = tc.get("info_dict", {})
            params = tc.get("params", {})
            if not info_dict.get("id"):
                raise Exception("Test definition incorrect. 'id' key is not present")
            elif not info_dict.get("ext"):
                if params.get("skip_download") and params.get(
                    "ignore_no_formats_error"
                ):
                    continue
                raise Exception(
                    "Test definition incorrect. "
                    "The output file cannot be known. 'ext' key is not present"
                )

        if "skip" in test_case:
            print_skipping(test_case["skip"])
            return
        for other_ie in other_ies:
            if not other_ie.working():
                print_skipping(
                    f"test depends on {other_ie.ie_key()}IE, marked as not WORKING"
                )
                return

        params = get_params(test_case.get("params", {}))
        params["outtmpl"] = tname + "_" + params["outtmpl"]
        if is_playlist and "playlist" not in test_case:
            params.setdefault("extract_flat", "in_playlist")
            params.setdefault("playlistend", test_case.get("playlist_mincount"))
            params.setdefault("skip_download", True)

        ydl = YoutubeDL(params, auto_init=False)
        ydl.add_default_info_extractors()
        finished_hook_called = set()

        def _hook(status):
            if status["status"] == "finished":
                finished_hook_called.add(Path(status["filename"]))

        ydl.add_progress_hook(_hook)
        expect_warnings(ydl, test_case.get("expected_warnings", []))

        def get_tc_filename(tc) -> Path:
            return Path(ydl.prepare_filename(dict(tc.get("info_dict", {}))))

        res_dict = None

        def try_rm_tcs_files(tcs: Optional[Sequence] = None) -> None:
            if tcs is None:
                tcs = test_cases
            for tc in tcs:
                tc_filename = get_tc_filename(tc)
                self.assertFalse(tc_filename.is_dir())
                tc_filename.unlink(missing_ok=True)
                tc_filename.with_name(tc_filename.name + ".part").unlink(
                    missing_ok=True
                )
                tc_filename.with_suffix(".info.json").unlink(missing_ok=True)

        try_rm_tcs_files()
        succeeded_testcases = []
        try:
            try_num = 1
            while True:
                try:
                    # We're not using .download here since that is just a shim
                    # for outside error handling, and returns the exit code
                    # instead of the result dict.
                    res_dict = ydl.extract_info(
                        test_case["url"],
                        force_generic_extractor=params.get(
                            "force_generic_extractor", False
                        ),
                    )
                except (DownloadError, ExtractorError) as err:
                    # Check if the exception is not a network related one
                    if not err.exc_info[0] in (
                        compat_urllib_error.URLError,
                        socket.timeout,
                        UnavailableVideoError,
                        compat_http_client.BadStatusLine,
                    ) or (
                        err.exc_info[0] == compat_HTTPError
                        and err.exc_info[1].code == 503
                    ):
                        raise

                    if try_num == RETRIES:
                        report_warning(
                            f"{tname} failed due to network errors, skipping..."
                        )
                        return

                    print(f"Retrying: {try_num} failed tries\n\n##########\n\n")

                    try_num += 1
                else:
                    break

            if is_playlist:
                self.assertTrue(res_dict["_type"] in ["playlist", "multi_video"])
                self.assertTrue("entries" in res_dict)
                DownloadTestcase.expect_info_dict(
                    self, res_dict, test_case.get("info_dict", {})
                )

            if "playlist_mincount" in test_case:
                DownloadTestcase.assertGreaterEqual(
                    self,
                    len(res_dict["entries"]),
                    test_case["playlist_mincount"],
                    f"Expected at least {test_case['playlist_mincount']:d} "
                    f"in playlist {test_case['url']}, "
                    f"but got only {len(res_dict['entries']):d}",
                )
            if "playlist_count" in test_case:
                self.assertEqual(
                    len(res_dict["entries"]),
                    test_case["playlist_count"],
                    f"Expected {test_case['playlist_count']:d} entries "
                    f"in playlist {test_case['url']}, "
                    f"but got {len(res_dict['entries']):d}.",
                )
            if "playlist_duration_sum" in test_case:
                got_duration = sum(e["duration"] for e in res_dict["entries"])
                self.assertEqual(test_case["playlist_duration_sum"], got_duration)

            # Generalize both playlists and single videos to unified format for
            # simplicity
            if "entries" not in res_dict:
                res_dict["entries"] = [res_dict]

            for tc_num, tc in enumerate(test_cases):
                tc_res_dict = res_dict["entries"][tc_num]
                # First, check test cases' data against extracted data alone
                DownloadTestcase.expect_info_dict(
                    self, tc_res_dict, tc.get("info_dict", {})
                )
                # Now, check downloaded file consistency
                tc_filename = get_tc_filename(tc)

                info_json_fn = tc_filename.with_suffix(".info.json")
                self.assertTrue(
                    info_json_fn.exists(), f"Missing info file {info_json_fn}"
                )
                info_dict = json.loads(info_json_fn.read_text())
                # write formatted json back
                info_json_fn.write_text(json.dumps(info_dict, indent=4))
                if not test_case.get("params", {}).get("skip_download", False):
                    self.assertTrue(
                        tc_filename.exists(), msg=f"Missing file {tc_filename}"
                    )
                    self.assertTrue(
                        tc_filename in finished_hook_called,
                        (tc_filename, finished_hook_called),
                    )
                    expected_minsize = tc.get("file_minsize", 10000)
                    if expected_minsize is not None:
                        if params.get("test"):
                            expected_minsize = max(expected_minsize, 10000)
                        got_fsize = os.path.getsize(tc_filename)
                        DownloadTestcase.assertGreaterEqual(
                            self,
                            got_fsize,
                            expected_minsize,
                            f"Expected {tc_filename} to be at least "
                            f"{format_bytes(expected_minsize)}, "
                            f"but it's only {format_bytes(got_fsize)} ",
                        )
                    if "md5" in tc:
                        md5_for_file = _file_md5(tc_filename)
                        self.assertEqual(tc["md5"], md5_for_file)
                # Finally, check test cases' data again but this time against
                # extracted data from info JSON file written during processing
                DownloadTestcase.expect_info_dict(
                    self, info_dict, tc.get("info_dict", {})
                )
                succeeded_testcases.append(tc)
        finally:
            try_rm_tcs_files(succeeded_testcases)
            if is_playlist and res_dict is not None and res_dict.get("entries"):
                # Remove all other files that may have been extracted if the
                # extractor returns full results even with extract_flat
                res_tcs = [{"info_dict": e} for e in res_dict["entries"]]
                try_rm_tcs_files(res_tcs)

    return test_template


# And add them to TestDownload
tests_counter = {}
for test_case in defs:
    name = test_case["name"]
    i = tests_counter.get(name, 0)
    tests_counter[name] = i + 1
    test_name = f"test_{name}_{i}" if i else f"test_{name}"
    test_method = generator(test_case, test_name)
    test_method.__name__ = str(test_name)
    ie_list = test_case.get("add_ie")
    test_method.add_ie = ie_list and ",".join(ie_list)
    setattr(TestDownload, test_method.__name__, test_method)
    del test_method


def batch_generator(name, num_tests):
    def test_template(self):
        for i in range(num_tests):
            getattr(self, f"test_{name}_{i}" if i else f"test_{name}")()

    return test_template


for name, num_tests in tests_counter.items():
    test_method = batch_generator(name, num_tests)
    test_method.__name__ = f"test_{name}_all"
    test_method.add_ie = ""
    setattr(TestDownload, test_method.__name__, test_method)
    del test_method

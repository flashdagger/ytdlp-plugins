#!/usr/bin/env python
# -*- coding: UTF-8 -*-

from ytdlp_plugins._helper import DownloadTestcase


class TestDownloadTestcase(DownloadTestcase):
    def test_string_ok(self):
        test_cases = (
            ("default", "foo", "foo"),
            ("startswith", "startswith:foo", "foobar"),
            ("regex", r"re:\w+", "foobar"),
            ("contains", "contains:foo", "barfoobar"),
            ("md5", "md5:acbd18db4cc2f85cedef654fccc4a4d8", "foo"),
            ("count", "count:3", [1, 2, 3]),
            ("mincount", "mincount:3", dict.fromkeys([1, 2, 3, 4])),
            ("maxcount", "maxcount:4", [1, 2, 3]),
        )

        for field, expected, got in test_cases:
            with self.subTest("string case", field=field):
                self.expect_value(got=got, expected=expected, field=field)

    def test_string_fail(self):
        test_cases = (
            ("default", "foo", "bar", r" : expected"),
            ("startswith", "startswith:foo", "bar", r" : .+ does not start with"),
            ("regex", r"re:\d+", "foo", r" : .+ does not match"),
            ("contains", "contains:foo", "bar", r" : .+ does not contain"),
            ("md5", "md5:badeaffe", "foo", r" : expected .+ got 'md5:"),
            ("count", "count:4", [1, 2, 3], r" : expected exactly 4"),
            ("count", "count:4", "aaaa", r" : expected a list or a dict"),
            ("mincount", "mincount:5", [1, 2, 3, 4], r" : expected at least 5"),
            ("maxcount", "maxcount:2", [1, 2, 3], r" : expected not more than 2"),
        )

        for field, expected, got, regex in test_cases:
            with self.subTest("string case", field=field):
                with self.assertRaisesRegex(AssertionError, regex):
                    self.expect_value(got=got, expected=expected, field=field)

    def test_container_ok(self):
        test_cases = (
            ("dict", dict(foo="bar"), dict(foo="bar", bar="foo")),
            ("list", [1, 2, 3, 4], [1, 2, 3, 4]),
            ("type", int, 777),
            ("type", bool, True),
            ("other", repr, repr),
        )

        for field, expected, got in test_cases:
            with self.subTest("type case", field=field):
                self.expect_value(got=got, expected=expected, field=field)

    def test_container_fail(self):
        test_cases = (
            ("dict", dict(foo="bar"), dict(bar="foo"), r" : expected .+ got None"),
            ("list len", [1, 2, 3, 4], [1, 2, 3], r" : expected a list of length"),
            ("list value", [1, 2, 3, 4], [1, 2, 3, 5], r" : expected \d+, got \d+"),
            ("type1", int, "foo", " : expected type"),
            ("type2", bool, 777, " : expected type"),
            ("other", repr, compile, " : expected.+got"),
        )

        for field, expected, got, regex in test_cases:
            with self.subTest(field=field):
                with self.assertRaisesRegex(AssertionError, regex):
                    self.expect_value(got=got, expected=expected, field=field)

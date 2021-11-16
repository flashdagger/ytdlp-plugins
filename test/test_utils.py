#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import unittest

from ytdlp_plugins import utils


class TestUtils(unittest.TestCase):
    def test_estimate_filesize(self):
        tbr = 12345
        item = dict(tbr=tbr)
        formats = [dict(item)]

        utils.estimate_filesize(formats, None)
        self.assertEqual(item, formats[0])

        utils.estimate_filesize(formats, 0)
        self.assertEqual(item, formats[0])

        utils.estimate_filesize(formats, 10)
        self.assertIn("filesize_approx", formats[0])
        self.assertIsInstance(formats[0]["filesize_approx"], (int, float))

    def test_estimate_filesize_1(self):
        tbr = 12345
        item = dict(tbr=tbr, filesize=10 * tbr)
        formats = [dict(item)]

        utils.estimate_filesize(formats, 10)
        self.assertEqual(item, formats[0])

    def test_parsed_url_with_regex(self):
        url = "https://www.brighteon.com/new-search?query=woo&page=2&uploaded=all"
        parsed_url = utils.ParsedURL(url, regex=r".*/(?P<base>[\w-]+)")

        self.assertEqual(parsed_url.scheme, "https")
        self.assertEqual(parsed_url.netloc, "www.brighteon.com")
        self.assertEqual(parsed_url.path, "/new-search")
        self.assertEqual(parsed_url.params, "")
        self.assertEqual(parsed_url.fragment, "")

        expected_query = dict(query="woo", page="2", uploaded="all")
        self.assertDictEqual(parsed_url.query(), expected_query)
        self.assertEqual(parsed_url.query("query"), "woo")
        self.assertEqual(parsed_url.query("not_found", True), True)

        expected_match = dict(base="new-search")
        self.assertDictEqual(parsed_url.match(), expected_match)
        self.assertEqual(parsed_url.match("base"), "new-search")
        self.assertEqual(parsed_url.match(1), "new-search")
        with self.assertRaises(IndexError):
            parsed_url.match("not_found")

    def test_parsed_url_without_regex(self):
        url = "https://www.brighteon.com/new-search?query=woo&page=2&uploaded=all"
        parsed_url = utils.ParsedURL(url)
        self.assertIs(parsed_url.match(), None)
        self.assertIs(parsed_url.match("any_key"), None)

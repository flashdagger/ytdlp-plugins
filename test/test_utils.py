#!/usr/bin/env python
# -*- coding: UTF-8 -*-
import unittest

from ytdlp_plugins import utils


class TestPlugins(unittest.TestCase):
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

    def test_estimate_filesize2(self):
        tbr = 12345
        item = dict(tbr=tbr, filesize=10 * tbr)
        formats = [dict(item)]

        utils.estimate_filesize(formats, 10)
        self.assertEqual(item, formats[0])

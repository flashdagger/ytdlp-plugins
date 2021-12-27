#!/usr/bin/env python
# -*- coding: UTF-8 -*-

"""
    For testing purposes this module contains classes that lead to
    name collisions with internal extractors as well as extractors
    from other plugins
"""

from yt_dlp.extractor.bitchute import BitChuteIE as _BitChuteIE

from .example import DummyPluginIE as _DummyPluginIE


# original BitChuteIE defined in yt_dlp.extractor.bitchute
class BitChuteIE(_BitChuteIE):
    _VALID_URL = _BitChuteIE._VALID_URL
    IE_NAME = "bitchute:override"
    _TESTS = ()


# already defined in .example
class DummyPluginIE(_DummyPluginIE):
    _VALID_URL = _DummyPluginIE._VALID_URL

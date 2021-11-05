# coding: utf-8
"""
    For testing purposes this module contains classes that lead to
    name collisions with internal extractors as well as extractors
    from other plugins
"""
from yt_dlp.extractor.bitchute import BitChuteIE as _BitChuteIE

from .example import ExamplePluginIE as _ExamplePluginIE


# original BitChuteIE defined in yt_dlp.extractor.bitchute
class BitChuteIE(_BitChuteIE):
    _TESTS = ()


# already defined in .example
class ExamplePluginIE(_ExamplePluginIE):
    pass

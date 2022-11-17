#!/usr/bin/env python
# -*- coding: UTF-8 -*-
__all__ = ["ExamplePluginIE", "FailingPluginIE"]


from yt_dlp.extractor.common import InfoExtractor
from yt_dlp.utils import ExtractorError, determine_ext

from ytdlp_plugins.probe import probe_media

# ℹ️ Instructions on making extractors can be found at:
# 🔗 https://github.com/yt-dlp/yt-dlp/blob/master/CONTRIBUTING.md#adding-support-for-a-new-site


class PrivatePluginIE(InfoExtractor):
    _VALID_URL = r"^privateplugin:(?P<id>\w+)"


class DummyPluginIE(InfoExtractor):
    _VALID_URL = r"^dummyplugin:(?P<id>\w+)"


class ExamplePluginIE(InfoExtractor):
    __version__ = "2021.11.05"
    _WORKING = True
    IE_NAME = "example"
    IE_DESC = "example for an external plugin"
    IE_BUG_REPORT = (
        "please report this issue on https://github.com/flashdagger/ytdlp-plugins"
    )
    _VALID_URL = r"^exampleplugin:(?P<id>\w+)"
    _TESTS = [
        {
            "url": "exampleplugin:hello",
            "info_dict": {"id": "hello", "title": "hello", "ext": "gif"},
            "md5": "c8ef5a107fbe3ae7dc0f6bdfeeddf009",
            "params": {"nocheckcertificate": True},
        }
    ]

    def _real_extract(self, url):
        self.to_screen(f"URL {url!r} sucessfully captured")
        media_id = self._match_id(url)
        media_url = "https://c.tenor.com/y2Mxb8a-DwAAAAAM/davizinmakermeuovo.gif"
        ext = determine_ext(media_url)

        return {"id": media_id, "title": media_id, "url": media_url, "ext": ext}


class FailingPluginIE(InfoExtractor):
    """
    for test purposes only
    class raises unexpected ExtractorError
    instead yt-dlp standard bug report message the one from class
    should be displayed
    """

    __version__ = "2021.11.05"
    _WORKING = True
    IE_BUG_REPORT = (
        "please report this issue on https://github.com/flashdagger/ytdlp-plugins"
    )
    _VALID_URL = r"^failingplugin:(?P<id>\w+)"

    def _real_extract(self, url):
        raise ExtractorError("Should not happen")


class FFProbePluginIE(InfoExtractor):
    _WORKING = True
    IE_NAME = "ffprobe"
    IE_DESC = "extract media format with ffprobe"
    _VALID_URL = r"^ffprobe:(?P<id>https?://.+)"

    def _real_extract(self, _url):
        url = self._match_id(_url)
        formats = probe_media(self, url)

        return {
            "id": self._generic_id(url),
            "title": self._generic_title(url),
            "duration": formats[0].get("duration") if formats else None,
            "formats": formats,
        }

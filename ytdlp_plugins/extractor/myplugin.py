#!/usr/bin/env python
# -*- coding: UTF-8 -*-

from yt_dlp.extractor.common import InfoExtractor


# ℹ️ Instructions on making extractors can be found at:
# 🔗 https://github.com/yt-dlp/yt-dlp/blob/master/CONTRIBUTING.md#adding-support-for-a-new-site


class MyPluginIE(InfoExtractor):
    __version__ = "0.1.0"
    _WORKING = True
    IE_NAME = "myplugin"
    IE_DESC = "minimal example for an external yt-dlp plugin"
    IE_BUG_REPORT = (
        "please report this issue on https://github.com/<user>/<repo>"
    )
    _VALID_URL = r"^myplugin:(?P<id>\w+)"

    def _real_extract(self, url):
        self.to_screen(f"URL {url!r} sucessfully captured")
        video_id = self._match_id(url)

        return {"id": video_id, "title": "<title>", "url": "http://myplugin.com", "ext": "mp4"}

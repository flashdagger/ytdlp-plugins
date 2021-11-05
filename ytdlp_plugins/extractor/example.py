# coding: utf-8

from yt_dlp.extractor.common import InfoExtractor
from yt_dlp.utils import determine_ext, ExtractorError


# ℹ️ Instructions on making extractors can be found at:
# 🔗 https://github.com/yt-dlp/yt-dlp/blob/master/CONTRIBUTING.md#adding-support-for-a-new-site


class ExamplePluginIE(InfoExtractor):
    _WORKING = True
    IE_NAME = "example"
    IE_DESC = "example for an external plugin"
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
        self.to_screen('URL "%s" sucessfully captured' % url)
        media_id = self._match_id(url)
        media_url = "https://c.tenor.com/y2Mxb8a-DwAAAAAM/davizinmakermeuovo.gif"
        ext = determine_ext(media_url)
        raise ExtractorError("oops", video_id=media_id)

        return {"id": media_id, "title": media_id, "url": media_url, "ext": ext}

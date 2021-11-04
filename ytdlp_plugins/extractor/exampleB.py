# coding: utf-8

# ⚠ Don't use relative imports
from yt_dlp.extractor.common import InfoExtractor

# ℹ️ Instructions on making extractors can be found at:
# 🔗 https://github.com/yt-dlp/yt-dlp/blob/master/CONTRIBUTING.md#adding-support-for-a-new-site


class TestPluginBIE(InfoExtractor):
    _WORKING = True
    IE_DESC = "example for an external plugin"
    _VALID_URL = r"^testpluginB:(?P<id>\w+)"
    _TESTS = [
        {
            "url": "testpluginB:testurl",
            "info_dict": {"id": "testurl", "title": "testurl", "ext": "mp4"},
            "params": {
                "skip_download": True,
            },
        }
    ]

    def _real_extract(self, url):
        self.to_screen('URL "%s" sucessfully captured' % url)
        id = self._match_id(url)

        return {"id": id, "title": id, "url": url, "ext": "mp4"}

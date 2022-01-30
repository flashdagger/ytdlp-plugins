# coding: utf-8
import re

from yt_dlp.extractor.common import InfoExtractor
from yt_dlp.extractor.peertube import PeerTubeIE
from yt_dlp.utils import UnsupportedError

__version__ = "2022.01.30"


# pylint: disable=abstract-method
class Auf1IE(InfoExtractor):
    IE_NAME = "auf1"
    _VALID_URL = r"""(?x)
                    https?://
                        (?:www\.)?
                        (?:auf1\.tv/)
                        (?:[^/]+/)*
                        (?P<id>[^/]+)
                    """

    _TESTS = [
        {
            "url": "https://auf1.tv/nachrichten-auf1/"
            "ampelkoalition-eine-abrissbirne-fuer-deutschland/",
            "info_dict": {
                "id": "rKjpWNnocoARnj4pQMRKXQ",
                "title": "Ampelkoalition: Eine Abrissbirne für Deutschland?",
                "description": "md5:9265dda76d30e842e1f75aa3cb3e3884",
                "ext": "mp4",
                "thumbnail": r"re:https://(:?auf1.)?gegenstimme.tv/static/thumbnails/[\w-]+.jpg",
                "timestamp": 1638446905,
                "upload_date": "20211202",
                "uploader": "AUF1.TV",
                "uploader_id": "25408",
                "duration": 818,
                "view_count": int,
                "like_count": int,
                "dislike_count": int,
                "categories": ["News & Politics"],
            },
            "params": {"skip_download": True, "nocheckcertificate": True},
        },
        {
            # playlist
            "url": "https://auf1.tv/videos",
            "info_dict": {
                "id": "videos",
                "title": "AUF1.TV - Alle Videos",
            },
            "params": {"skip_download": True},
            "playlist_mincount": 400,
        },
    ]

    def _real_extract(self, url):
        page_id = self._match_id(url)
        base_url = self._search_regex(r"(https?://[^/]+)", url, "base url")
        webpage = self._download_webpage(url, video_id=page_id)

        payloadjs_path = self._html_search_regex(
            r'<link\s+[^>]*href="(/[^"]+/payload.js)', webpage, "payload.js url"
        )

        payloadjs_string = self._download_webpage(
            f"{base_url}{payloadjs_path}",
            video_id=page_id,
            encoding="unicode_escape",
            note="Downloading payload.js",
        )

        peertube_urls = [
            f"peertube:{netloc}:{video_id}"
            for netloc, video_id in re.findall(
                r'"https?://([^/]+)/videos/embed/([^"?]+)', payloadjs_string
            )
        ]

        if not peertube_urls:
            raise UnsupportedError(url)

        if len(peertube_urls) == 1:
            return self.url_result(peertube_urls[0], ie=PeerTubeIE.ie_key())

        return self.playlist_from_matches(
            peertube_urls,
            playlist_id=page_id,
            playlist_title=self._og_search_title(webpage),
            ie=PeerTubeIE.ie_key(),
        )

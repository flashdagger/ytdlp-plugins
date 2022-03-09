# coding: utf-8
import re
import time

from yt_dlp.extractor.common import InfoExtractor
from yt_dlp.extractor.peertube import PeerTubeIE
from yt_dlp.utils import (
    UnsupportedError,
    OnDemandPagedList,
    ExtractorError,
    parse_iso8601,
    parse_duration,
    clean_html,
)

__version__ = "2022.03.09"


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

    peertube_extract_url = None
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
        {  # JSON API without payload.js
            "url": "https://auf1.tv/stefan-magnet-auf1/"
            "heiko-schoening-chaos-und-krieg-gehoeren-leider-zu-deren-plan/",
            "info_dict": {
                "id": "dVk8Q3VNMLi7b7uhyuSSp6",
                "ext": "mp4",
                "title": "Heiko Schöning: „Chaos und Krieg gehören leider zu deren Plan“",
                "description": "md5:6fb9e7eb469fc544223018a2ff3c998c",
                "timestamp": 1646671536,
                "uploader": "AUF1.TV",
                "uploader_id": "25408",
                "upload_date": "20220307",
                "channel": "AUF1.TV",
                "channel_url": "https://gegenstimme.tv/video-channels/auf1.tv",
                "duration": 2089,
                "view_count": int,
                "like_count": int,
                "dislike_count": int,
                "tags": [],
                "categories": ["News & Politics"],
            },
            "params": {"skip_download": True, "nocheckcertificate": True},
            "expected_warnings": ["payload.js"],
        },
        {
            # playlist for category
            "url": "https://auf1.tv/schicksale-auf1/",
            "info_dict": {
                "id": "schicksale-auf1",
                "title": "Schicksale AUF1",
            },
            "params": {"skip_download": True},
            "playlist_mincount": 3,
            "expected_warnings": ["Too Many Requests"],
        },
        {
            # playlist for all videos
            "url": "https://auf1.tv/videos",
            "info_dict": {
                "id": "all_videos",
                "title": "AUF1.TV - Alle Videos",
            },
            "params": {"skip_download": True},
            "playlist_mincount": 5,
            "expected_warnings": ["Too Many Requests"],
        },
    ]

    def call_api(self, endpoint, video_id=None, fatal=True):
        return self._download_json(
            f"https://auf1.at/api/{endpoint}", video_id=video_id, fatal=fatal
        )

    def call_with_retries(
        self, operation, default=None, sleep_duration_s=5.0, max_duration_s=30.0
    ):
        start = time.time()
        while True:
            try:
                return operation()
            except ExtractorError as exc:
                time_left = start + max_duration_s - time.time()
                error_code = getattr(exc.cause, "code", 0)
                if error_code in {429} and time_left > 0.0:
                    self.report_warning(
                        f"HTTP Error 429: Too Many Requests "
                        f"({time_left:.1f} seconds left)"
                    )
                    time.sleep(sleep_duration_s)
                    continue
                self.report_warning(exc)
                return default

    def peertube_extract(self, url):
        if self.peertube_extract_url is None:
            peertube_extractor = self._downloader.get_info_extractor(
                PeerTubeIE.ie_key()
            )
            self.peertube_extract_url = getattr(peertube_extractor, "_real_extract")

        return self.call_with_retries(
            lambda: self.peertube_extract_url(url),
            sleep_duration_s=3.0,
            max_duration_s=5.0,
        )

    @staticmethod
    def parse_urls(html_string):
        return [
            f"peertube:{netloc}:{video_id}"
            for netloc, video_id in re.findall(
                r"[\"']https?://([^/]+)/videos/embed/([^\"'?]+)", html_string
            )
        ]

    def all_videos_from_api(self):
        all_videos = self.call_with_retries(
            lambda: self.call_api("getVideos", video_id="all_videos")
        )
        valid_videos = [item for item in all_videos if item.get("public_id")]

        def fetch_page(page_number: int):
            if page_number >= len(valid_videos):
                return
            self.to_screen(f"Downloading metadata {page_number} of {len(valid_videos)}")
            item = valid_videos[page_number]
            public_id = item["public_id"]
            backup_info = {
                "id": public_id,
                "url": "//",
                "title": item.get("title"),
                "description": clean_html(item.get("text")),
                "duration": parse_duration(item.get("duration")),
                "timestamp": parse_iso8601(item.get("published_at")),
            }
            info = self.call_with_retries(
                lambda: self.call_api(f"getContent/{public_id}", public_id),
            )
            if not info:
                yield backup_info
                return

            urls = self.parse_urls(repr(info.get("videoUrl")))
            if not urls:
                yield backup_info
                return

            ie_info = self.peertube_extract(urls[0])
            if ie_info:
                yield ie_info if ie_info else backup_info

        return self.playlist_result(
            OnDemandPagedList(fetch_page, 1),
            playlist_id="all_videos",
            playlist_title="AUF1.TV - Alle Videos",
        )

    def _real_extract(self, url):
        page_id = self._match_id(url)

        if page_id == "videos":
            return self.all_videos_from_api()

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
            errnote="payload.js",
            fatal=False,
        )

        if payloadjs_string:
            peertube_urls = self.parse_urls(payloadjs_string)
        else:
            info = self.call_api(f"getContent/{page_id}", page_id)
            peertube_urls = self.parse_urls(repr(info.get("videoUrl")))

        if not peertube_urls:
            raise UnsupportedError(url)

        if len(peertube_urls) == 1:
            return self.peertube_extract(peertube_urls[0])

        return self.playlist_result(
            [self.peertube_extract(url) for url in peertube_urls],
            playlist_id=page_id,
            playlist_title=self._og_search_title(webpage),
        )

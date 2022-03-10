# coding: utf-8
import json
import re
import time

from yt_dlp.extractor.common import InfoExtractor
from yt_dlp.extractor.peertube import PeerTubeIE
from yt_dlp.utils import (
    ExtractorError,
    parse_iso8601,
    parse_duration,
    clean_html,
    traverse_obj,
    js_to_json,
    UnsupportedError,
)

__version__ = "2022.03.09"


# pylint: disable=abstract-method
class Auf1IE(InfoExtractor):
    IE_NAME = "auf1"
    _VALID_URL = r"""(?x)
                    https?://
                        (?:www\.)?
                        (?:auf1\.tv/)
                        (?P<category>[^/]+/)?
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
            "url": "https://auf1.tv/nachrichten-auf1/",
            "info_dict": {
                "id": "nachrichten-auf1",
                "title": "Nachrichten AUF1",
            },
            "params": {"skip_download": True},
            "playlist_mincount": 300,
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
            "playlist_mincount": 400,
            "expected_warnings": ["Too Many Requests"],
        },
    ]

    @staticmethod
    def parse_urls(html_string):
        return [
            f"peertube:{netloc}:{video_id}"
            for netloc, video_id in re.findall(
                r"[\"']https?://([^/]+)/videos/embed/([^\"'?]+)", html_string
            )
        ]

    @staticmethod
    def sparse_info(metadata):
        return {
            "id": metadata.get("public_id", "unknown"),
            "url": metadata.get("videoUrl"),
            "title": metadata.get("title"),
            "description": clean_html(metadata.get("text")),
            "duration": parse_duration(metadata.get("duration")),
            "timestamp": parse_iso8601(metadata.get("published_at") or None),
        }

    def parse_url(self, url):
        urls = self.parse_urls(repr(url))
        return urls[0] if urls else None

    def call_api(self, endpoint, video_id=None, fatal=True):
        return self._download_json(
            f"https://auf1.at/api/{endpoint}", video_id=video_id, fatal=fatal
        )

    def call_with_retries(
        self,
        operation,
        fatal=True,
        sleep_duration_s=5.0,
        max_duration_s=30.0,
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
                        f"Retrying due to too many requests. "
                        f"Will give up in {time_left:.1f} seconds."
                    )
                    time.sleep(sleep_duration_s)
                    continue

                if not fatal:
                    self.report_warning(exc)
                    return False
                raise

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

    def playlist_from_entries(self, all_videos, **kwargs):
        with open("videos.json", "w") as fd:
            json.dump(all_videos, fd, indent=4)
        entries = []

        for item in all_videos:
            public_id = item.get("public_id")
            if not public_id:
                continue
            category = traverse_obj(item, ("show", "public_id"), default="video")
            entries.append(
                {
                    "_type": "url",
                    "ie_key": self.ie_key(),
                    **self.sparse_info(item),
                    "url": f"//auf1.tv/{category}/{public_id}/",
                }
            )

        return self.playlist_result(
            entries,
            **kwargs,
        )

    def _real_extract(self, url):
        def entry(info):
            peertube_url = self.parse_url(info.get("videoUrl"))
            peertube_info = (
                self.peertube_extract(peertube_url) if peertube_url else None
            )
            return peertube_info if peertube_info else self.sparse_info(info)

        category, page_id = self._match_valid_url(url).groups()

        if category is None and page_id == "videos":
            return self.playlist_from_entries(
                self.call_with_retries(
                    lambda: self.call_api("getVideos", video_id="all_videos")
                ),
                playlist_id="all_videos",
                playlist_title="AUF1.TV - Alle Videos",
            )

        if category:
            return entry(
                self.call_with_retries(
                    lambda: self.call_api(f"getContent/{page_id}", page_id)
                )
            )

        base_url = self._search_regex(r"(https?://[^/]+)", url, "base url")
        webpage = self._download_webpage(url, video_id=page_id)
        title = self._og_search_title(webpage)
        payloadjs_path = self._html_search_regex(
            r'<link\s+[^>]*href="(/[^"]+/payload.js)', webpage, "payload.js url"
        )
        payloadjs_string = self._download_webpage(
            f"{base_url}{payloadjs_path}",
            video_id=page_id,
            note="Downloading payload.js",
            errnote="payload.js",
        )

        match = re.match(r".*?\(function\(([^)]+)", payloadjs_string)
        keys = match.group(1).split(",") if match else ()

        match = re.match(r".*}\((.*)\){3};", payloadjs_string)
        values = json.loads(f"[{match.group(1)}]") if match else ()
        js_vars = {key: json.dumps(value) for key, value in zip(keys, values)}

        match = re.match(r".*?contents:(\[{.+}]).+}}]", payloadjs_string)
        if not match:
            raise UnsupportedError(url)

        video_data = json.loads(
            js_to_json(
                match.group(1),
                vars=js_vars,
            )
        )
        return self.playlist_from_entries(
            video_data, playlist_id=page_id, playlist_title=title
        )

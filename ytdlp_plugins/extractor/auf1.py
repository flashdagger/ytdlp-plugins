# coding: utf-8
import json
import re
import time
from shlex import shlex
from urllib.error import HTTPError

from yt_dlp.extractor.common import InfoExtractor
from yt_dlp.extractor.peertube import PeerTubeIE
from yt_dlp.utils import (
    ExtractorError,
    parse_iso8601,
    parse_duration,
    clean_html,
    traverse_obj,
    UnsupportedError,
    urljoin,
    base_url,
    js_to_json,
)

__version__ = "2022.09.16"


class JSHLEX(shlex):
    def __init__(self, instream):
        super().__init__(
            instream=instream, infile=None, posix=True, punctuation_chars=False
        )
        self.whitespace = ", \t\r\n"
        self.whitespace_split = True

    def __next__(self):
        value = super().__next__()
        try:
            json.loads(value)
        except json.JSONDecodeError:
            quote_escaped = value.replace('"', '\\"')
            value = f'"{quote_escaped}"'
        return value


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
            "params": {"skip_download": True},
            "expected_warnings": [
                "Retrying due to too many requests.",
                "The read operation timed out",
                "JSON API",
            ],
        },
        {  # JSON API without payload.js
            "url": "https://auf1.tv/stefan-magnet-auf1/"
            "heiko-schoening-chaos-und-krieg-gehoeren-leider-zu-deren-plan/",
            "info_dict": {
                "id": "dVk8Q3VNMLi7b7uhyuSSp6",
                "ext": "mp4",
                "title": "Heiko Schöning: „Chaos und Krieg gehören leider zu deren Plan“",
                "description": "md5:6fb9e7eb469fc544223018a2ff3c998c",
                "timestamp": int,
                "uploader": str,
                "uploader_id": str,
                "upload_date": "20220307",
                "channel": str,
                "channel_url": "contains:/video-channels/auf1.tv",
                "duration": 2089,
                "view_count": int,
                "like_count": int,
                "dislike_count": int,
                "tags": [],
                "categories": ["News & Politics"],
            },
            "params": {"skip_download": True},
            "expected_warnings": [
                "Retrying due to too many requests.",
                "The read operation timed out",
                "JSON API",
            ],
        },
        {
            # playlist for category
            "url": "https://auf1.tv/nachrichten-auf1/",
            "info_dict": {
                "id": "nachrichten-auf1",
                "title": "Nachrichten AUF1",
                "description": "md5:5b1f113270133adfd94f6ae3014e3d6f",
            },
            "params": {"skip_download": True},
            "playlist_mincount": 300,
            "expected_warnings": [
                "Retrying due to too many requests.",
                "The read operation timed out",
                "JSON API",
            ],
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
            "expected_warnings": [
                "Retrying due to too many requests.",
                "JSON API",
            ],
        },
    ]

    @staticmethod
    def parse_url(url: str):
        if not url:
            return None
        match = re.match(r"^https?://([^/]+)/videos/embed/([^?]+)", url)
        # pylint: disable=consider-using-f-string
        return "peertube:{}:{}".format(*match.groups()) if match else None

    @staticmethod
    def sparse_info(metadata):
        return {
            "id": metadata.get("public_id", "unknown"),
            "url": metadata.get("videoUrl"),
            "title": metadata.get("title"),
            "description": clean_html(traverse_obj(metadata, "text", "preview_text")),
            "duration": parse_duration(metadata.get("duration")),
            "timestamp": parse_iso8601(metadata.get("published_at") or None),
            "thumbnail": metadata.get("thumbnail_url"),
        }

    def call_api(self, endpoint, video_id=None, fatal=True):
        return self._download_json(
            f"https://admin.auf1.tv/api/{endpoint}",
            video_id=video_id,
            fatal=fatal,
            errnote="JSON API",
        )

    def call_with_retries(
        self,
        operation,
        http_error_map=None,
    ):
        http_error_map = http_error_map or {}
        max_duration_s = 30.0
        sleep_duration_s = 5.0
        attempt_count = 0
        while True:
            start = time.time()
            try:
                return operation()
            except ExtractorError as exc:
                attempt_count += 1
                errorcode = None
                if isinstance(exc.cause, HTTPError):
                    errorcode = exc.cause.code
                    sleep_duration_s = float(
                        exc.cause.headers.get("retry-after", sleep_duration_s)
                    )
                if max_duration_s < 0.0:
                    self.report_warning(f"Giving up after {attempt_count} attempts.")
                elif errorcode == 429:
                    self.report_warning(
                        f"Retrying in {sleep_duration_s:.0f} seconds due to too many requests."
                    )
                    max_duration_s -= time.time() - start
                    time.sleep(sleep_duration_s)
                    continue
                for errors, exception in http_error_map.items():
                    if isinstance(errors, int):
                        errors = {errors}
                    if errorcode in errors:
                        raise exception from exc
                raise

    def peertube_extract(self, url):
        if self.peertube_extract_url is None:
            peertube_extractor = self._downloader.get_info_extractor(
                PeerTubeIE.ie_key()
            )
            self.peertube_extract_url = getattr(peertube_extractor, "_real_extract")

        return self.call_with_retries(
            lambda: self.peertube_extract_url(url),
        )

    def playlist_from_entries(self, all_videos, **kwargs):
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

    def _payloadjs(self, url, page_id):
        webpage = self._download_webpage(url, page_id)
        payloadjs_url = self._search_regex(
            r'href="([^"]+/payload.js)"', webpage, "payload url"
        )
        payloadjs_url = urljoin(base_url(url), payloadjs_url)
        payload_js = self._download_webpage(
            payloadjs_url, page_id, note="Downloading payload.js"
        )

        match = re.match(
            r"""(?x)
                .*
                \(function\ *\( (?P<vars>[^)]*) \)
                \{\ *return\ * (?P<metadata>\{.+}) .*}
                \( (?P<values>.*) \){3}
            """,
            payload_js,
        )
        if match is None:
            raise ExtractorError("Failed parsing payload.js")

        variables, metadata, values = match.groups()
        var_mapping = dict(zip(variables.split(","), JSHLEX(values)))

        control_character_mapping = dict.fromkeys(range(32))
        js_string = js_to_json(metadata, vars=var_mapping).translate(
            control_character_mapping
        )
        return json.loads(js_string)

    def _metadata(self, url, *, page_id, method="api"):
        if method == "api":
            return self.call_with_retries(
                lambda: self.call_api(f"getContent/{page_id}", page_id),
                http_error_map={500: UnsupportedError(url)},
            )
        payload = self._payloadjs(url, page_id)
        return payload["data"][0]["payload"]

    def _real_extract(self, url):
        category, page_id = self._match_valid_url(url).groups()

        # single video
        if category:
            try:
                metadata = self._metadata(url, page_id=page_id, method="api")
            except ExtractorError as exc:
                self.report_warning(exc, page_id)
                metadata = self._metadata(url, page_id=page_id, method="payloadjs")
            peertube_url = self.parse_url(metadata.get("videoUrl"))
            return (
                self.peertube_extract(peertube_url)
                if peertube_url
                else self.sparse_info(metadata)
            )

        # video playlist
        if page_id == "videos":
            return self.playlist_from_entries(
                self.call_with_retries(
                    lambda: self.call_api("getVideos", video_id="all_videos"),
                ),
                playlist_id="all_videos",
                playlist_title="AUF1.TV - Alle Videos",
            )

        try:
            metadata = self.call_with_retries(
                lambda: self.call_api(f"getShow/{page_id}", page_id),
            )
        except ExtractorError as exc:
            self.report_warning(exc, page_id)
            metadata = self._metadata(url, page_id=page_id, method="payloadjs")

        return self.playlist_from_entries(
            metadata.get("contents"),
            playlist_id=page_id,
            playlist_title=metadata.get("name"),
            description=clean_html(metadata.get("description")),
        )

# coding: utf-8
import json
import re
import time
from contextlib import suppress
from shlex import shlex
from urllib.error import HTTPError

from yt_dlp.extractor.common import InfoExtractor
from yt_dlp.utils import (
    ExtractorError,
    OnDemandPagedList,
    clean_html,
    parse_duration,
    parse_iso8601,
    traverse_obj,
)

__version__ = "2023.09.15"


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
                    (?:https?:)?//
                        (?:www\.)?
                        (?:auf1\.tv/)
                        (?P<category>[^/]+/)?
                        (?P<id>[^/]+)
                    """

    _TESTS = [
        {  # JSON API without _payload.json
            "url": "https://auf1.tv/stefan-magnet-auf1/heiko-schoening-chaos-und-krieg-gehoeren-leider-zu-deren-plan/",
            "info_dict": {
                "id": "heiko-schoening-chaos-und-krieg-gehoeren-leider-zu-deren-plan",
                "ext": "mp4",
                "title": "Heiko Schöning: „Chaos und Krieg gehören leider zu deren Plan“",
                "description": "md5:620fae46004a2adc7f4c92fe73442748",
                "timestamp": 1646743800,
                "upload_date": "20220308",
                "duration": 2089,
            },
            "params": {"skip_download": True},
        },
        {
            # playlist for category
            "url": "https://auf1.tv/nachrichten-auf1/",
            "info_dict": {
                "id": "nachrichten-auf1",
                "title": "Nachrichten AUF1",
                "description": "md5:e472da8d2bc2fa45e7e9ffe996ee1381",
            },
            "playlist_mincount": 100,
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
            "playlist_mincount": 200,
            "expected_warnings": [
                "Retrying due to too many requests.",
                "JSON API",
            ],
        },
    ]

    @staticmethod
    def parse_url(url: dict):
        _format = {}
        if "src" in url:
            _format["url"] = url["src"]
        label = url.get("label")
        if label:
            _format["format_id"] = label
            height = re.match(r"(\d+)p", label)
            if height:
                _format["height"] = int(height.group(1))

        return _format

    def sparse_info(self, metadata):
        peertube_urls = traverse_obj(
            metadata, ("videoData", "urls", "peertube"), default=()
        )
        return {
            "id": metadata.get("public_id", "unknown"),
            "title": metadata.get("title"),
            "description": clean_html(traverse_obj(metadata, "text", "preview_text")),
            "duration": parse_duration(metadata.get("duration")),
            "timestamp": parse_iso8601(metadata.get("published_at") or None),
            "thumbnail": metadata.get("thumbnail_url"),
            "formats": [fmt for fmt in map(self.parse_url, peertube_urls) if fmt],
        }

    def call_api(self, endpoint, video_id=None, fatal=True):
        return self._download_json(
            f"https://auf1.tv/api/{endpoint}",
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

    def _payloadjson(self, url, page_id):
        payload_json = self._download_json(
            f"{url}/_payload.json",
            page_id,
            note="Downloading _payload.json",
            errnote="Unable to download _payload.json",
        )
        if not isinstance(payload_json, list):
            raise ExtractorError("unexpected _payload.json format")

        def resolve(idx: int):
            assert isinstance(idx, int)
            item = payload_json[idx]
            _type = type(item)

            if _type in transformation:
                assert idx not in seen_idx
                seen_idx.add(idx)
                return transformation[_type](item)

            return item

        transformation = {
            dict: lambda _item: {_key: resolve(_idx) for _key, _idx in _item.items()},
            list: lambda _item: [resolve(_idx) for _idx in _item],
        }
        seen_idx = set()
        return resolve(3)

    def _metadata(self, url, *, page_id, method="api"):
        if method == "api":
            return self.call_with_retries(
                lambda: self.call_api(f"getContent/{page_id}", page_id),
                http_error_map={500: ExtractorError("JSON API failed (500)")},
            )
        return self._payloadjson(url, page_id)

    def _real_extract(self, url):
        category, page_id = self._match_valid_url(url).groups()
        metadata = {}

        # single video
        if category:
            try:
                metadata = self._metadata(url, page_id=page_id, method="api")
            except ExtractorError as exc:
                self.report_warning(exc, page_id)

            if not metadata:
                metadata = self._metadata(url, page_id=page_id, method="_payload.json")

            info = self.sparse_info(metadata or {})
            return info

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


# pylint: disable=abstract-method
class Auf1RadioIE(InfoExtractor):
    IE_NAME = "auf1:radio"
    _VALID_URL = r"""(?x)
                    https?://
                        (?:www\.)?
                        auf1\.radio
                        (?: / 
                            (?P<category>[^/]+/)?
                            (?P<id>[^/]+)
                        )?
                        /?
                    """

    _TESTS = [
        {
            "url": "https://auf1.radio/nachrichten-auf1/worte-der-hoffnung-ein-sammelband-der-mut-macht/",
            "md5": "3a0d00dd473f46b387678621420fad8e",
            "info_dict": {
                "id": "worte-der-hoffnung-ein-sammelband-der-mut-macht",
                "ext": "mp3",
                "title": "Worte der Hoffnung: Ein Sammelband, der Mut macht",
                "description": "md5:3102f277e87e1baafc7f09242b66a071",
                "duration": 70,
                "timestamp": 1669539605,
                "upload_date": "20221127",
                "thumbnail": "re:https://auf1.*.jpg",
            },
        },
        {
            # playlist for category
            "url": "https://auf1.radio/nachrichten-auf1/",
            "info_dict": {
                "id": "nachrichten-auf1",
                "title": "Nachrichten AUF1",
            },
            "playlist_mincount": 50,
        },
        {
            # playlist for all media
            "url": "https://auf1.radio/",
            "info_dict": {
                "id": "all",
                "title": "all",
            },
            "playlist_mincount": 50,
        },
    ]

    MP3_FORMAT = {
        "ext": "mp3",
        "acodec": "mp3",
        "vcodec": "none",
        "asr": 48000,
        "tbr": 64,
        "abr": 64,
        "format": "MP2/3 (MPEG audio layer 2/3)",
    }

    def call_api(self, endpoint, **kwargs):
        kwargs.setdefault("errnote", "JSON API")
        return self._download_json(
            f"https://auf1.radio/api/{endpoint}",
            **kwargs,
        )

    def formats(self, url: str, duration):
        format_info = {"url": url}
        if url.endswith(".mp3"):
            format_info.update(self.MP3_FORMAT)  # type: ignore
            if duration:
                format_info["filesize_approx"] = duration * 8000
        return [format_info]

    def entry_from_info(self, info, media_id):
        return {
            "id": info.get("content_public_id", media_id),
            "title": info["title"],
            "description": info.get("summary"),
            "duration": info.get("duration"),
            "timestamp": parse_iso8601(info.get("created_at")),
            "thumbnail": info.get("thumbnail")
            and f"https://auf1.tv/images/{info['thumbnail']}",
            "formats": self.formats(info.get("audio_url"), info.get("duration")),
        }

    def entries_from_playlist(self, playlist_id):
        endpoint = "" if playlist_id == "all" else "getShow/"

        def fetch(page, _last_page):
            page_note = (
                f"{page + 1}/{_last_page}" if isinstance(_last_page, int) else page + 1
            )
            return self.call_api(
                f"{endpoint}{playlist_id}",
                query={"page": page + 1},
                video_id=playlist_id,
                note=f"Downloading page {page_note}",
            )

        first_page = fetch(0, None)
        last_page = first_page.get("last_page", "NA")
        page_size = first_page.get("per_page", len(first_page.get("data", ())))
        playlist_title = playlist_id
        with suppress(KeyError, IndexError):
            if playlist_id != "all":
                playlist_title = first_page["data"][0]["show_name"]

        def load_page(index):
            info = fetch(index, last_page) if index > 0 else first_page
            for media_info in info["data"]:
                audiofile = media_info.get("audiofile")
                if audiofile:
                    media_info["audio_url"] = f"https://auf1.radio/storage/{audiofile}"
                yield self.entry_from_info(media_info, playlist_id)

        return self.playlist_result(
            entries=OnDemandPagedList(load_page, page_size),
            playlist_id=playlist_id,
            playlist_title=playlist_title,
            playlist_count=first_page.get("total", "NA"),
        )

    def _real_extract(self, url):
        category, page_id = self._match_valid_url(url).groups()

        if category:
            info = self.call_api(f"get/{page_id}", video_id=page_id)
            if not info:
                raise ExtractorError("not available")
            return self.entry_from_info(info, page_id)

        return self.entries_from_playlist(page_id or "all")

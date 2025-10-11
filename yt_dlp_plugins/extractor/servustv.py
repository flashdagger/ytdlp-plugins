# coding: utf-8
import re
from itertools import count
from typing import Any, Dict, Optional, Sequence
from urllib.parse import parse_qsl, urlparse

from yt_dlp.extractor.common import InfoExtractor
from yt_dlp.utils import (
    ExtractorError,
    GeoRestrictedError,
    LazyList,
    UnsupportedError,
    get_element_by_id,
    int_or_none,
    parse_iso8601,
    traverse_obj,
    unescapeHTML,
    urljoin,
)

__version__ = "2025.10.11"
AnyDict = Dict[str, Any]


class ServusTVIE(InfoExtractor):
    IE_NAME = "servustv"
    _VALID_URL = r"""(?x)
                    https?://
                        (?:www\.)?servustv\.com/
                        (?: [\w-]+ / [abkpv] / )? (?P<id>[A-Za-z0-9-]+)
                    """

    PAGE_SIZE = 20
    BASE_URL = "https://servustv.com/"
    _GEO_COUNTRIES = ["AT", "DE", "CH", "LI", "LU", "IT"]
    _GEO_BYPASS = False

    _API_URL = "https://api-player.redbull.com/stv/servus-tv-playnet"
    _ASSET_API_URL = "https://www.servustv.com/api/v1/media-asset/landing-page-archive/"
    _LOGO = "https://presse.servustv.com/Content/76166/cfbc6a68-fd77-46d6-8149-7f84f76efe5c/"

    _LIVE_URLS = {
        "AT": "https://dms.redbull.tv/v5/destination/stv/stv-linear"
        "/personal_computer/http/at/de_AT/playlist.m3u8",
        "DE": "https://dms.redbull.tv/v5/destination/stv/stv-linear"
        "/personal_computer/http/de/de_DE/playlist.m3u8",
    }

    _TESTS = [
        {
            # new URL schema
            "url": "https://www.servustv.com/wissen/v/aal97b7ww3e22jrymhse/",
            "info_dict": {
                "id": "aal97b7ww3e22jrymhse",
                "ext": "mp4",
                "title": "Bunte Antike?",
                "series": "P.M. Wissen",
                "season_number": 1,
                "episode_number": 176,
                "description": "Thema u.a.: Wie Forscher Farben aus der R\u00f6merzeit wieder leuchten lassen",
                "duration": 2837,
                "timestamp": int,
                "categories": ["P.M. Wissen"],
                "age_limit": 0,
                "upload_date": "20240229",
                "is_live": False,
                "thumbnail": r"re:^https?://.*\.jpeg",
            },
            "params": {
                "skip_download": True,
                "format": "bestvideo",
                "geo_bypass_country": "DE",
            },
        },
        {
            # playlist
            "url": "https://www.servustv.com/volkskultur/b/ich-bauer/aa-1qcy94h3s1w11/",
            "info_dict": {
                "id": "aa-1qcy94h3s1w11",
                "title": "startswith:Ich, Bauer",
                "description": "md5:04cd98226e5c07ca50d0dc90f4a27ea1",
            },
            "playlist": [
                {
                    "info_dict": {
                        "id": "aat544m75z6xm4p93c7z",
                        "title": "Jetzt oder nie!",
                        "series": "Ich, Bauer",
                        "season_number": 3,
                        "episode_number": 4,
                        "description": "md5:483c6d034a102caab4398826358b76af",
                        "timestamp": int,
                        "upload_date": "20220101",
                    },
                },
                {
                    "info_dict": {
                        "id": "aarj7qi65ikr255p922y",
                        "title": "Wir suchen keine Idylle",
                        "series": "Ich, Bauer",
                        "season_number": 4,
                        "episode_number": 2,
                        "description": "md5:8375fc598827c13c36bda1a98f89fa22",
                        "timestamp": int,
                        "upload_date": "20220101",
                    },
                },
            ],
            "params": {
                "geo_bypass_country": "AT",
                "format": "bestvideo",
                "skip_download": True,
                "playlist_items": "2,4",
            },
        },
        {
            # main live stream
            "url": "https://www.servustv.com/jetzt-live/",
            "info_dict": {
                "id": str,
                "ext": "mp4",
                "title": str,
                "description": str,
                "duration": None,
                "timestamp": (type(None), int),
                "upload_date": (type(None), str),
                "is_live": True,
                "age_limit": (type(None), int),
                "thumbnail": (type(None), str),
            },
            "params": {
                "skip_download": True,
                "outtmpl": "livestream.%(ext)s",
                "format": "bestvideo/best",
            },
        },
        {
            # topic live stream
            "url": "https://www.servustv.com/natur/k/natur-kanal/pn5265d2299446c/",
            "info_dict": {
                "id": str,
                "ext": "re:m3u8|m4a",
                "title": str,
                "description": str,
                "duration": None,
                "timestamp": (type(None), int),
                "upload_date": (type(None), str),
                "is_live": True,
                "age_limit": (type(None), int),
                "thumbnail": (type(None), str),
                "format_id": r"re:audio-(en|de)$",
            },
            "params": {
                "skip_download": True,
                "outtmpl": "livestream.%(ext)s",
                "format": "bestaudio",
            },
        },
    ]
    JSON_OBJ_ID = "__NEXT_DATA__"

    def __init__(self, downloader=None):
        super().__init__(downloader=downloader)
        self.country_override = None
        self.timezone = "Europe/Vienna"

    @property
    def country_code(self) -> str:
        return self.country_override or self._GEO_COUNTRIES[0]

    def initialize(self):
        geo_bypass_country = self.get_param("geo_bypass_country")
        if geo_bypass_country:
            self.country_override = geo_bypass_country.upper()
            self.to_screen(f"Set countrycode to {self.country_code!r}")
        super().initialize()

    def _og_search_title(self, html: str, **kwargs) -> str:
        site_name = self._og_search_property("site_name", html, default=None)
        title = super()._og_search_title(html, **kwargs)
        if site_name and title:
            title = title.replace(f" - {site_name}", "", 1)

        return title

    def _playlist_meta(self, page_data: AnyDict, webpage: str) -> AnyDict:
        return {
            "playlist_id": page_data.get("slug"),
            "playlist_title": traverse_obj(page_data, ("title", "rendered"))
            or self._og_search_title(webpage, default=None),
            "playlist_description": traverse_obj(
                page_data, "stv_short_description", "stv_teaser_description"
            )
            or self._og_search_description(webpage, default=None),
        }

    def _hls_duration(self, formats: Sequence[AnyDict]) -> Optional[float]:
        for fmt in formats:
            if not fmt["url"].endswith(".m3u8"):
                return None
            m3u8_doc = self._download_webpage(
                fmt["url"],
                None,
                note="Probing HLS stream duration",
                fatal=False,
            )
            matches = re.findall(
                r"(?m)^#EXT(?:INF:(\d*\.?\d+),|-X-ENDLIST)", m3u8_doc or ""
            )
            if matches and matches[-1] == "":
                return sum(map(float, matches[:-1]))
            break

        return None

    def _download_formats(self, video_url: str, video_id: str, is_live=False):
        if not video_url:
            return [], {}

        try:
            formats, subtitles = self._extract_m3u8_formats_and_subtitles(
                video_url,
                video_id=None,
                errnote="Stream not available",
            )
        except ExtractorError as exc:
            raise ExtractorError(exc.msg, video_id=video_id, expected=True) from exc

        for fmt in formats:
            if "height" in fmt:
                fmt["format_id"] = f"{fmt['height']}p"
            elif fmt.get("vcodec") == "none":
                if not is_live and "acodec" not in fmt:
                    fmt["acodec"] = "mp4a.40.2"
                    fmt["asr"] = 44100
                    fmt["ext"] = "m4a"
                if fmt.get("language"):
                    fmt["format_id"] = f"audio-{fmt['language']}"

        return formats, subtitles

    @staticmethod
    def program_info(info: AnyDict) -> AnyDict:
        program_info = {"series": info.get("label"), "chapter": info.get("chapter")}
        match = re.match(r"\D+(\d+)", info.get("season", ""))
        if match:
            program_info["season_number"] = int(match[1])
        match = re.match(r"Episode\s+(\d+)(?:\s+-(.*))?", info.get("chapter", ""))
        if match:
            program_info["episode_number"] = int(match[1])
            program_info["chapter"] = match[2] and match[2].strip()
        return program_info

    def _entry_by_id(self, video_id: str, video_url=None, is_live=False) -> AnyDict:
        info = self._download_json(
            self._API_URL,
            query={"videoId": video_id.upper(), "timeZone": self.timezone},
            video_id=video_id,
            fatal=False,
            expected_status=(400, 404, 500),
        ) or {"error": "Server Error", "message": "Bad JSON Response"}

        if "error" in info:
            raise ExtractorError(
                ": ".join((info["error"], info["message"])), expected=True
            )

        if video_url is None:
            video_url = info.get("videoUrl")
        live_status = "is_live" if is_live else "not_live"
        errors = ", ".join(info.get("playabilityErrors", ()))
        if errors and not video_url:
            errormsg = f'{info.get("title", "Unknown")} - {errors}'
            if "NOT_YET_AVAILABLE" in errors:
                live_status = "is_upcoming"
            if "GEO_BLOCKED" in errors:
                countries = None
                blocked_countries = info.get("blockedCountries")
                if blocked_countries:
                    countries = set(self._GEO_COUNTRIES) - set(blocked_countries)
                raise GeoRestrictedError(errormsg, countries=countries)
            self.raise_no_formats(errormsg, expected=True)

        formats, subtitles = self._download_formats(
            video_url, video_id, is_live=is_live
        )
        program_info = self.program_info(info)
        duration = info.get("duration")
        if is_live:
            duration = None
        elif not duration and live_status == "not_live":
            duration = self._hls_duration(formats)
            live_status = "was_live" if duration else "is_live"

        return {
            "id": video_id,
            "title": info.get("title", "").strip() or program_info.get("chapter"),
            **program_info,
            "description": info.get("description"),
            "thumbnail": info.get("poster", self._LOGO),
            "duration": duration,
            "timestamp": parse_iso8601(info.get("currentSunrise")),
            "release_timestamp": parse_iso8601(
                traverse_obj(
                    info,
                    ("playabilityErrorDetails", "NOT_YET_AVAILABLE", "availableFrom"),
                    default=None,
                )
            ),
            "live_status": live_status,
            "categories": [info["label"]] if info.get("label") else [],
            "age_limit": int(
                self._search_regex(
                    r"(?:^|\s)(\d\d?)(?:\s|$)",
                    info.get("maturityRating", "0"),
                    "age_limit",
                    default="0",
                )
            ),
            "formats": formats,
            "subtitles": subtitles,
        }

    def _url_entry_from_post(self, post: AnyDict, **kwargs) -> AnyDict:
        duration = int_or_none(traverse_obj(post, ("stv_duration", "raw")))
        return self.url_result(
            urljoin(self.BASE_URL, post["link"]),
            video_id=post.get("slug"),
            video_title=unescapeHTML(
                traverse_obj(
                    post,
                    ("title", "rendered"),
                    "stv_short_title",
                    "stv_teaser_title",
                )
            ),
            description=traverse_obj(post, "stv_teaser_description"),
            duration=duration and duration * 0.001,
            **kwargs,
        )

    def _live_stream_from_schedule(
        self, aa_id: str, stream_id: Optional[str]
    ) -> AnyDict:
        if self.country_code in self._LIVE_URLS:
            video_url = self._LIVE_URLS[self.country_code]
        else:
            video_url = self._LIVE_URLS["DE"].replace(
                "/de_DE/", f"/de_{self.country_code}/"
            )

        if stream_id:
            video_url = video_url.replace("/stv-linear/", f"/{stream_id}/")

        return self._entry_by_id(aa_id.lower(), video_url=video_url, is_live=True)

    @staticmethod
    def _page_data(json_obj: AnyDict) -> AnyDict:
        for item in (
            "videoData",
            "data",
        ):
            page_data = traverse_obj(
                json_obj, f"props/pageProps/{item}".split("/"), default={}
            )
            if page_data:
                break
        return page_data

    def _entries_from_api_query(self, category: str, video_id: str):
        total = 0
        for page in count(1):
            info = self._download_json(
                self._ASSET_API_URL,
                query={
                    "geo": self.country_code,
                    "currentPage": page,
                    "category": category,
                    "newCurrentFilter": "allevideos",
                },
                video_id=video_id,
                note=f"Downloading entries page {page}",
            )
            items = info.get("items", ())
            total += len(items)
            yield from (self._url_entry_from_post(post) for post in items)
            if total >= info.get("count", 0):
                return

    def _real_extract(self, url: str) -> AnyDict:
        video_id = self._match_id(url)
        url_parts = urlparse(url)
        url_query = {key.lower(): value for key, value in parse_qsl(url_parts.query)}

        # server accepts tz database names
        # see https://en.wikipedia.org/wiki/List_of_tz_database_time_zones
        if "timezone" in url_query:
            self.timezone = url_query["timezone"]
            self.to_screen(f"Set timezone to {self.timezone!r}")

        # single video
        if "/v/" in url_parts.path:
            return self._entry_by_id(video_id)

        webpage = self._download_webpage(url, video_id=video_id)
        try:
            json_obj = self._parse_json(
                get_element_by_id(self.JSON_OBJ_ID, webpage), video_id
            )
        except TypeError as exc:
            raise ExtractorError("Cannot extract metadata.") from exc

        if self.country_override is None:
            self.country_override = traverse_obj(
                json_obj, "props/pageProps/geo".split("/"), default=None
            )

        # find livestreams
        channel_id = traverse_obj(
            json_obj, "props/pageProps/initChannelId".split("/"), default=None
        )

        if channel_id:
            for item in traverse_obj(
                json_obj, "props/pageProps/miniGuideData".split("/"), default=()
            ):
                if item["channelId"] == channel_id:
                    page_data = item["pageData"]
                    break
            else:
                raise UnsupportedError(url)

            return self._live_stream_from_schedule(page_data["stv_id"], channel_id)

        page_data = self._page_data(json_obj)
        if not page_data:
            raise UnsupportedError(url)

        # create playlist from api query
        litems = self._entries_from_api_query(
            category=page_data["stv_category_name"], video_id=video_id
        )
        return self.playlist_result(
            LazyList(litems),
            **self._playlist_meta(page_data, webpage),
        )

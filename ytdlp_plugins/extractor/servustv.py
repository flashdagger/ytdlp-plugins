# coding: utf-8
import re
from operator import itemgetter
from urllib.parse import unquote_plus

from yt_dlp.extractor.common import InfoExtractor
from yt_dlp.utils import (
    ExtractorError,
    GeoRestrictedError,
    OnDemandPagedList,
    UnsupportedError,
    get_element_by_id,
    parse_iso8601,
    traverse_obj,
)
from ytdlp_plugins.utils import estimate_filesize, ParsedURL

__version__ = "2021.11.20"


class ServusIE(InfoExtractor):
    IE_NAME = "servustv"
    _VALID_URL = r"""(?x)
                    https?://
                        (?:www\.)?servustv.com
                        /[\w-]+/(?:v|[abp]/[\w-]+)
                        /(?P<id>[A-Za-z0-9-]+)
                    """

    PAGE_SIZE = 20
    _GEO_COUNTRIES = ["AT", "DE", "CH", "LI", "LU", "IT"]
    _GEO_BYPASS = False

    _API_URL = "https://api-player.redbull.com/stv/servus-tv"
    _QUERY_API_URL = "https://backend.servustv.com/wp-json/rbmh/v2/query-filters/query/"
    _LIVE_URLS = {
        "AT": "https://dms.redbull.tv/v4/destination/stv/stv-linear"
        "/personal_computer/chrome/at/de_AT/playlist.m3u8",
        "DE": "https://dms.redbull.tv/v4/destination/stv/stv-linear"
        "/personal_computer/chrome/de/de_DE/playlist.m3u8",
    }

    _TESTS = [
        {
            # new URL schema
            "url": "https://www.servustv.com/wissen/v/aa-273cebhp12111/",
            "info_dict": {
                "id": "aa-273cebhp12111",
                "ext": "mp4",
                "title": "Was lebt im Steinbruch?",
                "description": "md5:a905b6135469cf60a07d4d0ae1e8d49a",
                "duration": 271,
                "timestamp": int,
                "categories": ["P.M. Wissen"],
                "age_limit": 0,
                "upload_date": "20211111",
                "is_live": False,
                "thumbnail": r"re:^https?://.*\.jpg",
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
                "id": "116155",
                "title": "Ich, Bauer",
                "description": "md5:04cd98226e5c07ca50d0dc90f4a27ea1",
            },
            "playlist": [
                {
                    "info_dict": {
                        "id": "aa-22rankb9h2112",
                        "title": "Der Engelswand-Bauer",
                        "description": "md5:22149f1593cac13703dc31f87162badb",
                        "timestamp": int,
                        "upload_date": "20210501",
                    },
                },
                {
                    "info_dict": {
                        "id": "aa-24hxt6ycw1w12",
                        "title": "Ich, Bauer",
                        "description": "md5:01335fd4f02d66d6ae9af2c5387d18a3",
                        "timestamp": int,
                        "upload_date": "20210501",
                    },
                },
            ],
            "playlist_mincount": 10,
            "params": {
                "geo_bypass_country": "AT",
                "nocheckcertificate": True,
                "format": "bestvideo",
                "skip_download": True,
            },
        },
        {
            # live stream
            "url": "https://www.servustv.com/allgemein/p/jetzt-live/119753/",
            "info_dict": {
                "id": str,
                "ext": "mp4",
                "title": str,
                "description": str,
                "duration": None,
                "timestamp": int,
                "upload_date": str,
                "is_live": True,
                "thumbnail": r"re:^https?://.*\.jpg",
            },
            "params": {
                "skip_download": True,
                "outtmpl": "livestream.%(ext)s",
                "format": "bestvideo/best",
            },
        },
        {
            # test embedded links from 3rd party sites
            "url": "https://www.pm-wissen.com/videos/aa-24mus4g2w2112/",
            "info_dict": {
                "id": "aa-24mus4g2w2112",
                "title": "Wie kommt das Plastik aus dem Meer?",
            },
            "params": {
                "skip_download": True,
                "outtmpl": "%(title)s.%(id)s.%(ext)s",
                "format": "bestvideo/best",
            },
            "playlist_count": 1,
            "playlist": [
                {
                    "info_dict": {
                        "id": "aa-24mus4g2w2112",
                        "ext": "mp4",
                        "title": "Meer ohne Plastik?",
                        "description": str,
                        "duration": 418,
                        "timestamp": int,
                        "upload_date": str,
                        "is_live": False,
                        "thumbnail": r"re:^https?://.*\.jpg",
                    },
                },
            ],
        },
        {
            "url": "https://www.servustv.com/allgemein/v/aagevnv3syv5kuu8cpfq/",
            "only_matching": True,
        },
    ]

    def __init__(self, downloader=None):
        super().__init__(downloader=downloader)
        self.country_override = None
        self.timezone = "Europe/Vienna"

    @classmethod
    def _extract_urls(cls, webpage):
        return re.findall(
            r"""(?x)
                <link[^>]+href="
                (?P<url>https?://(?:www\.)?servustv.com/[\w-]+/(?:v|[bp]/[\w-]+)/[A-Za-z0-9-]+)
                [^"]*"
                """,
            webpage,
        )

    @property
    def country_code(self):
        return self.country_override or self._GEO_COUNTRIES[0]

    def initialize(self):
        geo_bypass_country = self.get_param("geo_bypass_country")
        if geo_bypass_country:
            self.country_override = geo_bypass_country.upper()
            self.to_screen(f"Set countrycode to {self.country_code!r}")
        super().initialize()

    def _auto_merge_formats(self, formats):
        requested_format = self.get_param("format")
        audio_only = [
            fmt["format_id"] for fmt in formats if fmt.get("vcodec") == "none"
        ]
        video_only = {
            fmt["format_id"] for fmt in formats if fmt.get("acodec") == "none"
        }

        if self._downloader and len(audio_only) == 1 and requested_format in video_only:
            requested_format = f"{requested_format}+{audio_only[0]}"
            self.to_screen(
                f"Adding audio stream {audio_only[0]!r} to video only format"
            )
            self._downloader.format_selector = self._downloader.build_format_selector(
                requested_format
            )

    def _download_formats(self, info, video_id):
        try:
            formats, subtitles = self._extract_m3u8_formats_and_subtitles(
                info["videoUrl"],
                video_id=None,
                entry_protocol="m3u8",
                errnote="Stream not available",
            )
        except ExtractorError as exc:
            raise ExtractorError(exc.msg, video_id=video_id, expected=True) from exc

        self._sort_formats(formats)
        for fmt in formats:
            if "height" in fmt:
                fmt["format_id"] = f"{fmt['height']}p"

        return formats, subtitles

    def _entry_by_id(self, video_id, video_url=None, is_live=False):
        info = (
            self._download_json(
                self._API_URL,
                query={"videoId": video_id.upper(), "timeZone": self.timezone},
                video_id=video_id,
                fatal=False,
                expected_status=(400, 404, 500),
            )
            or {"message": "Bad JSON Response"}
        )

        if "message" in info:
            raise ExtractorError(info["message"], expected=True)

        info.setdefault("videoUrl", video_url)
        errors = ", ".join(info.get("playabilityErrors", ()))
        errormsg = f'{info.get("title", "Unknown")} - {errors}'
        if "GEO_BLOCKED" in errors:
            countries = set(self._GEO_COUNTRIES) - set(info.get("blockedCountries", ()))
            raise GeoRestrictedError(errormsg, countries=countries)
        if errors and info.get("videoUrl") is None:
            raise ExtractorError(errormsg, expected=True)

        formats, subtitles = self._download_formats(info, video_id)
        duration = None if is_live else info.get("duration")
        estimate_filesize(formats, duration)
        self._auto_merge_formats(formats)

        return {
            "id": video_id,
            "title": info.get("title"),
            "description": info.get("description"),
            "thumbnail": info.get("poster"),
            "duration": duration,
            "timestamp": parse_iso8601(info.get("currentSunrise")),
            "is_live": is_live,
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

    def _live_stream_from_schedule(self, schedule):
        live_url = self._LIVE_URLS["AT"]
        for item in sorted(
            schedule, key=lambda x: x.get("is_live", False), reverse=True
        ):
            is_live = item.get("is_live", False)
            video_url = (
                self._LIVE_URLS.get(self.country_code, live_url) if is_live else None
            )
            return self._entry_by_id(
                item["aa_id"].lower(), video_url=video_url, is_live=is_live
            )

    def _paged_playlist_by_query(
        self, query_type, query_id, extra_query=(), extractor=None
    ):
        query = {
            query_type: query_id,
            "geo_override": self.country_code,
            "post_type": "media_asset",
            "filter_playability": "true",
            "per_page": self.PAGE_SIZE,
        }
        assert "per_page" not in extra_query
        query.update(extra_query)

        def fetch_page(page_number):
            query.update({"page": page_number + 1})
            info = self._download_json(
                self._QUERY_API_URL,
                query=query,
                video_id=f"{query_type}-{query_id}",
                note=f"Downloading entries "
                f"{page_number * self.PAGE_SIZE + 1}-{(page_number + 1) * self.PAGE_SIZE}",
            )

            for item in info["posts"]:
                if not traverse_obj(item, ("stv_duration", "raw")):
                    continue
                video_id, title, url = itemgetter("slug", "stv_short_title", "link")(
                    item
                )
                yield self.url_result(
                    url,
                    ie=extractor or self.ie_key(),
                    video_id=video_id,
                    video_title=title,
                )

        return OnDemandPagedList(fetch_page, self.PAGE_SIZE)

    def _og_search_title(self, html, **kwargs):
        site_name = self._og_search_property("site_name", html, default=None)
        title = super()._og_search_title(html, **kwargs)
        if site_name and title:
            title = title.replace(f" - {site_name}", "", 1)

        return title

    @staticmethod
    def _page_id(json_obj):
        for value in traverse_obj(json_obj, ("source", "data"), default={}).values():
            if isinstance(value, dict) and "id" in value:
                return value["id"]
        return None

    @staticmethod
    def taxonomy(json_obj, page_id, url):
        asset_paths = (
            ("source", "media_asset", str(page_id), "categories"),
            # ("source", "page", str(page_id), "asset_content_color"),
        )

        for path in asset_paths:
            asset_ids = traverse_obj(json_obj, path, default=())
            query_type = path[-1]
            query_id = asset_ids and asset_ids[0]
            if query_id:
                return query_type, query_id

        raise UnsupportedError(url)

    @staticmethod
    def _urls_from_blocks(blocks):
        flat_blocks = []
        for block in blocks:
            inner_blocks = block.get("innerBlocks")
            if isinstance(inner_blocks, list):
                flat_blocks.extend(inner_blocks)
            else:
                flat_blocks.append(block)
        links = (traverse_obj(block, ("post", "link")) for block in flat_blocks)
        return [url for url in links if url]

    def _real_extract(self, url):
        video_id = self._match_id(url)
        parsed_url = ParsedURL(url)
        url_query = {key.lower(): value for key, value in parsed_url.query().items()}

        # server accepts tz database names
        # see https://en.wikipedia.org/wiki/List_of_tz_database_time_zones
        if "timezone" in url_query:
            self.timezone = url_query["timezone"]
            self.to_screen(f"Set timezone to {self.timezone!r}")

        # single video
        if "/v/" in parsed_url.path:
            return self._entry_by_id(video_id)

        webpage = self._download_webpage(url, video_id=video_id)
        try:
            json_obj = self._parse_json(
                get_element_by_id("__FRONTITY_CONNECT_STATE__", webpage), video_id
            )
        except TypeError as exc:
            raise ExtractorError("Cannot extract metadata.") from exc

        if self.country_override is None:
            self.country_override = traverse_obj(
                json_obj, ("geolocation", "countryCode"), default=None
            )

        # find livestreams
        live_schedule = traverse_obj(
            json_obj,
            ("source", "page", video_id, "stv_live_player_schedule"),
            default=None,
        )
        if live_schedule:
            return self._live_stream_from_schedule(live_schedule)

        # create playlist from blocks
        page_id = self._page_id(json_obj)
        page_post = traverse_obj(json_obj, ("source", "post", str(page_id)), default={})
        urls = self._urls_from_blocks(page_post.get("blocks", ()))
        if urls:
            return self.playlist_from_matches(
                urls,
                playlist_id=page_post.get("slug"),
                playlist_title=traverse_obj(
                    page_post, ("title", "rendered"), default=page_post.get("slug")
                ),
                ie=self.ie_key(),
            )

        # finally create playlist from query
        query_type, query_id = self.taxonomy(json_obj, page_id, url)
        return self.playlist_result(
            self._paged_playlist_by_query(
                query_type=query_type,
                query_id=query_id,
                extra_query={"order": "desc", "orderby": "rbmh_playability"},
            ),
            playlist_id=str(page_id),
            playlist_title=self._og_search_title(webpage, default=None),
            playlist_description=self._og_search_description(webpage, default=None),
        )


class ServusSearchIE(ServusIE):
    IE_NAME = "servustv:search"
    _VALID_URL = r"""(?x)
                    https?://
                        (?:www\.)?servustv.com
                        /search
                        /(?P<id>[^/?#]+)
                        (?:/all-videos/\d+)?/?$
                    """

    _TESTS = [
        {
            # search playlist
            "url": "https://www.servustv.com/search/hubert+staller/",
            "info_dict": {
                "id": "hubert+staller",
                "title": "search: 'hubert staller'",
                "description": None,
            },
            "params": {"skip_download": True, "geo_bypass": False},
            "playlist_mincount": 1,
            "playlist_maxcount": 10,
        }
    ]

    def _real_extract(self, url):
        search_id = self._match_id(url)
        search_term = unquote_plus(search_id)

        return self.playlist_result(
            self._paged_playlist_by_query(
                query_type="search",
                query_id=search_term,
                extra_query={
                    "f[primary_type_group]": "all-videos",
                    "orderby": "rbmh_score_search",
                },
                extractor=ServusIE.ie_key(),
            ),
            playlist_id=search_id,
            playlist_title=f"search: '{search_term}'",
        )

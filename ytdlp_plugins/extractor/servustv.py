# coding: utf-8
import json
from operator import itemgetter

from yt_dlp.compat import (
    compat_parse_qs,
    compat_urllib_parse_unquote_plus,
    compat_urllib_parse_urlparse,
)
from yt_dlp.extractor.common import InfoExtractor
from yt_dlp.utils import (
    get_element_by_id,
    parse_iso8601,
    traverse_obj,
    ExtractorError,
    GeoRestrictedError,
    OnDemandPagedList,
)
from ytdlp_plugins.utils import estimate_filesize

__version__ = "2021.11.07"


class ServusTVIE(InfoExtractor):
    IE_NAME = "servustv"
    _VALID_URL = r"""(?x)
                    https?://
                        (?:www\.)?servustv.com
                        /[\w-]+/(?:v|[bp]/[\w-]+)
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
            "url": "https://www.servustv.com/aktuelles/v/aa-28jer1rfh1w11/",
            "info_dict": {
                "id": "aa-28jer1rfh1w11",
                "ext": "mp4",
                "title": "Die Top-Themen vom 05.11.",
                "description": "md5:c913d5aba429acf4ade46a181d9532f0",
                "duration": 587,
                "timestamp": int,
                "upload_date": "20211105",
                "is_live": False,
                "categories": ["Servus Nachrichten 19:00"],
                "age_limit": 0,
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
            "params": {"geo_bypass_country": "AT", "nocheckcertificate": True},
            "playlist_mincount": 10,
        },
        {
            "url": "https://www.servustv.com/allgemein/v/aagevnv3syv5kuu8cpfq/",
            "only_matching": True,
        },
        {
            "url": "https://www.servustv.com/allgemein/p/jetzt-live/119753/",
            "only_matching": True,
        },
    ]

    def __init__(self, downloader=None):
        super().__init__(downloader=downloader)
        self.country_override = None
        self.timezone = "Europe/Vienna"

    @property
    def country_code(self):
        return self.country_override or self._GEO_COUNTRIES[0]

    def _manage_formats(self, formats):
        audio_ids = set()
        video_ids = set()
        requested_format = self.get_param("format")

        self._sort_formats(formats)
        for fmt in formats:
            if "height" in fmt:
                fmt["format_id"] = f"{fmt['height']}p"
            (audio_ids if fmt.get("vcodec") == "none" else video_ids).add(
                fmt["format_id"]
            )

        if self._downloader and len(audio_ids) == 1 and requested_format in video_ids:
            audio_id = audio_ids.pop()
            requested_format = f"{requested_format}+{audio_id}"
            self.to_screen(f"Adding audio stream {audio_id!r} to format")
            self._downloader.format_selector = self._downloader.build_format_selector(
                requested_format
            )

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
            raise ExtractorError(info["message"], video_id=video_id, expected=True)

        info.setdefault("videoUrl", video_url)
        errors = ", ".join(info.get("playabilityErrors", ()))
        errormsg = f'{info.get("title", "Unknown")} - {errors}'
        if "GEO_BLOCKED" in errors:
            countries = set(self._GEO_COUNTRIES) - set(info.get("blockedCountries", ()))
            raise GeoRestrictedError(errormsg, countries=countries)
        if errors and info.get("videoUrl") is None:
            raise ExtractorError(errormsg, video_id=video_id, expected=True)

        try:
            formats, subtitles = self._extract_m3u8_formats_and_subtitles(
                info["videoUrl"],
                video_id=video_id,
                entry_protocol="m3u8",
                errnote="Stream not available",
            )
        except ExtractorError as exc:
            raise ExtractorError(exc.msg, video_id=video_id, expected=True) from exc

        self._manage_formats(formats)
        duration = None if is_live else info.get("duration")
        estimate_filesize(formats, duration)

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

    @staticmethod
    def _page_id(json_obj):
        for value in traverse_obj(json_obj, ("source", "data"), default={}).values():
            if isinstance(value, dict) and "id" in value:
                return value["id"]
        return None

    @staticmethod
    def _json_extract(webpage, video_id):
        json_string = get_element_by_id("__FRONTITY_CONNECT_STATE__", webpage)
        if not json_string:
            raise ExtractorError(
                "Missing HTML metadata", video_id=video_id, expected=True
            )

        try:
            return json.loads(json_string or "{}")
        except json.JSONDecodeError as exc:
            raise ExtractorError(
                "Bad JSON metadata", video_id=video_id, expected=False
            ) from exc

    def _real_extract(self, url):
        video_id = self._match_id(url)
        parsed_url = compat_urllib_parse_urlparse(url)
        url_query = {
            key.lower(): value[0]
            for key, value in compat_parse_qs(parsed_url.query).items()
        }

        geo_bypass_country = self.get_param("geo_bypass_country")
        if geo_bypass_country:
            self.country_override = geo_bypass_country.upper()
            self.to_screen(f"Set countrycode to {self.country_code!r}")

        # server accepts tz database names
        # see https://en.wikipedia.org/wiki/List_of_tz_database_time_zones
        if "timezone" in url_query:
            self.timezone = url_query["timezone"]
            self.to_screen(f"Set timezone to {self.timezone!r}")

        # single video
        if "/v/" in parsed_url.path:
            return self._entry_by_id(video_id)

        webpage = self._download_webpage(url, video_id=video_id)
        json_obj = self._json_extract(webpage, video_id=video_id)
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

        # create playlist
        page_id = self._page_id(json_obj)
        if page_id is None:
            raise ExtractorError("Missing page id", video_id=video_id)

        asset_paths = (
            ("source", "media_asset", str(page_id), "categories"),
            # ('source', 'page', str(page_id), 'asset_content_color'),
        )

        for *path, asset_name in asset_paths:
            asset_ids = traverse_obj(json_obj, (*path, asset_name), default=())
            if asset_ids:
                query_id, query_type = asset_ids[0], asset_name
                break
        else:
            raise ExtractorError(
                "Website contains no supported playlists",
                video_id=page_id,
                expected=True,
            )

        site_name = self._og_search_property("site_name", webpage, default=None)
        playlist_title = self._og_search_title(webpage, default=None)
        if site_name and playlist_title:
            playlist_title = playlist_title.replace(f" - {site_name}", "", 1)
        playlist_description = self._og_search_description(webpage, default=None)

        return self.playlist_result(
            self._paged_playlist_by_query(
                query_type=query_type,
                query_id=query_id,
                extra_query={"order": "desc", "orderby": "rbmh_playability"},
            ),
            playlist_id=str(page_id),
            playlist_title=playlist_title,
            playlist_description=playlist_description,
        )


class ServusSearchIE(ServusTVIE):
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
        search_term = compat_urllib_parse_unquote_plus(search_id)

        return self.playlist_result(
            self._paged_playlist_by_query(
                query_type="search",
                query_id=search_term,
                extra_query={
                    "f[primary_type_group]": "all-videos",
                    "orderby": "rbmh_score_search",
                },
                extractor=ServusTVIE.ie_key(),
            ),
            playlist_id=search_id,
            playlist_title=f"search: '{search_term}'",
        )


class PmWissenIE(ServusTVIE):
    IE_NAME = "pm-wissen"
    _VALID_URL = r"""(?x)
                    https?://
                        (?:www\.)?pm-wissen.com
                        /videos
                        /(?P<id>[aA]{2}-\w+)
                    """

    _TESTS = [
        {
            "url": "https://www.pm-wissen.com/videos/aa-24mus4g2w2112/",
            "only_matching": True,
        }
    ]

    def _real_extract(self, url):
        video_id = self._match_id(url)
        return self._entry_by_id(video_id)

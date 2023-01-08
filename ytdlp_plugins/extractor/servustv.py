# coding: utf-8
import re
from typing import Any, Dict, Iterator, Optional, Sequence, Tuple
from urllib.parse import parse_qsl, quote_plus, urlparse, urlunparse

from yt_dlp.extractor.common import InfoExtractor
from yt_dlp.utils import (
    ExtractorError,
    GeoRestrictedError,
    OnDemandPagedList,
    UnsupportedError,
    get_element_by_id,
    int_or_none,
    parse_iso8601,
    traverse_obj,
    unescapeHTML,
)

__version__ = "2022.11.15"
AnyDict = Dict[str, Any]


class ServusTVIE(InfoExtractor):
    IE_NAME = "servustv"
    _VALID_URL = r"""(?x)
                    https?://
                        (?:www\.)?servustv\.com/
                        (?:
                            videos | (?: [\w-]+/(?: v | [abkp]/[\w-]+ ) )
                        )
                        /(?P<id>[A-Za-z0-9-]+)
                    """

    PAGE_SIZE = 20
    _GEO_COUNTRIES = ["AT", "DE", "CH", "LI", "LU", "IT"]
    _GEO_BYPASS = False

    _API_URL = "https://api-player.redbull.com/stv/servus-tv"
    _LOGO = "https://presse.servustv.com/Content/76166/cfbc6a68-fd77-46d6-8149-7f84f76efe5c/"
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
                "series": "P.M. Wissen",
                "season_number": 1,
                "episode_number": 113,
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
            # old URL schema
            "url": "https://www.servustv.com/videos/aa-273cebhp12111/",
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
                "id": "aa-1qcy94h3s1w11",
                "title": "startswith:Ich, Bauer",
                "description": "md5:04cd98226e5c07ca50d0dc90f4a27ea1",
            },
            "playlist": [
                {
                    "info_dict": {
                        "id": "aa-22rankb9h2112",
                        "title": "Der Engelswand-Bauer",
                        "series": "Ich, Bauer",
                        "season_number": 2,
                        "episode_number": 3,
                        "description": "md5:22149f1593cac13703dc31f87162badb",
                        "timestamp": int,
                        "upload_date": "20210501",
                    },
                },
                {
                    "info_dict": {
                        "id": "aa-24hxt6ycw1w12",
                        "title": "Der Generationenhof",
                        "series": "Ich, Bauer",
                        "season_number": 3,
                        "episode_number": 1,
                        "description": "md5:01335fd4f02d66d6ae9af2c5387d18a3",
                        "timestamp": int,
                        "upload_date": "20210501",
                    },
                },
            ],
            "params": {
                "geo_bypass_country": "AT",
                "format": "bestvideo",
                "skip_download": True,
                "playlist_items": ":4",
            },
        },
        {
            # block post playlist
            "url": "https://www.servustv.com/aktuelles/a/"
            "corona-auf-der-suche-nach-der-wahrheit-teil-3-die-themen/193214/",
            "info_dict": {
                "id": "corona-auf-der-suche-nach-der-wahrheit-teil-3-die-themen",
                "title": "Corona – auf der Suche nach der Wahrheit, Teil 3: Die Themen",
                "description": "md5:a8a9c163eaf76f5ead9efac244e54935",
            },
            "playlist": [
                {
                    "info_dict": {
                        "id": "aa-28zh3u3dn2111",
                        "title": "Corona-Doku: Teil 3",
                        "description": "md5:5e020c2618a6d6d2b8a316891c8b8195",
                        "timestamp": int,
                        "upload_date": "20211222",
                    },
                },
                {
                    "info_dict": {
                        "id": "aa-27juub3a91w11",
                        "title": "Teil 1: Corona – auf der Suche nach der Wahrheit",
                        "description": "md5:b8de3e9d911bb2cdc0422cf720d795b5",
                        "timestamp": int,
                        "upload_date": "20210505",
                    },
                },
                {
                    "info_dict": {
                        "id": "aa-28a3dbyxh1w11",
                        "title": "Teil 2: Corona – auf der Suche nach der Wahrheit",
                        "description": "md5:9904e42bb1b99c731e651ed2276a87e6",
                        "timestamp": int,
                        "upload_date": "20210801",
                    },
                },
            ],
            "params": {
                "geo_bypass_country": "DE",
                "format": "bestvideo",
                "skip_download": True,
            },
        },
        {
            # main live stream
            "url": "https://www.servustv.com/allgemein/p/jetzt-live/119753/",
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
            "url": "https://www.servustv.com/natur/k/natur-kanal/269299/",
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
        {
            # block page playlist
            "url": "https://www.servustv.com/sport/p/motorsport/325/",
            "info_dict": {
                "id": "motorsport",
                "title": "Motorsport",
                "description": "md5:cc8e904daecaa697fcf03af3edb3c743",
            },
            "playlist_mincount": 2,
            "params": {
                "geo_bypass_country": "DE",
                "format": "bestvideo",
                "skip_download": True,
            },
        },
        {
            "url": "https://www.servustv.com/allgemein/v/aagevnv3syv5kuu8cpfq/",
            "only_matching": True,
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

    def _auto_merge_formats(self, formats: Sequence[AnyDict]):
        requested_format = self.get_param("format")
        audio_formats = [fmt for fmt in formats if fmt.get("vcodec") == "none"]
        audio_only = [fmt["format_id"] for fmt in audio_formats]
        video_only = {
            fmt["format_id"] for fmt in formats if fmt.get("acodec") == "none"
        }

        for fmt in audio_formats:
            if fmt["ext"] == "m3u8":
                fmt["ext"] = "m4a"

        if self._downloader and len(audio_only) == 1 and requested_format in video_only:
            requested_format = f"{requested_format}+{audio_only[0]}"
            self.to_screen(
                f"Adding audio stream {audio_only[0]!r} to video only format"
            )
            self._downloader.format_selector = self._downloader.build_format_selector(
                requested_format
            )

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

    def _download_formats(self, video_url: str, video_id: str):
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
            if fmt.get("vcodec") == "none" and fmt.get("language"):
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

        formats, subtitles = self._download_formats(video_url, video_id)
        self._auto_merge_formats(formats)

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
            post["link"],
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
        self, schedule: Sequence[AnyDict], stream_id: Optional[str]
    ) -> AnyDict:
        if self.country_code in self._LIVE_URLS:
            video_url = self._LIVE_URLS[self.country_code]
        else:
            video_url = self._LIVE_URLS["DE"].replace(
                "/de_DE/", f"/de_{self.country_code}/"
            )

        if not stream_id or stream_id.startswith("stvlive"):
            pass
        elif stream_id in {"nature", "science", "sports", "wintersport"}:
            video_url = video_url.replace("/stv-linear/", f"/{stream_id}/")
        else:
            raise ExtractorError(f"Unsupported live stream {stream_id!r}")

        for item in sorted(
            schedule, key=lambda x: x.get("is_live", False), reverse=True
        ):
            if item.get("is_live", False) is False:
                self.report_warning("Livestream might not be available")

            return self._entry_by_id(
                item["aa_id"].lower(), video_url=video_url, is_live=True
            )

        assert False, "Should not happen"

    def _paged_playlist_by_query(self, url: str, qid: str):
        url_parts = urlparse(url)
        url_query = dict(parse_qsl(url_parts.query))
        # pylint: disable=protected-access
        # noinspection PyProtectedMember
        query_api_url = urlunparse(url_parts._replace(query="", fragment=""))

        json_query = {
            **url_query,
            "geo_override": self.country_code,
            "post_type": "media_asset",
            # "filter_playability": "true",
            "per_page": self.PAGE_SIZE,
        }

        def fetch_page(page_number: int) -> Iterator[AnyDict]:
            json_query.update({"page": page_number + 1})
            info = self._download_json(
                query_api_url,
                query=json_query,
                video_id=qid,
                note=f"Downloading entries "
                f"{page_number * self.PAGE_SIZE + 1}-{(page_number + 1) * self.PAGE_SIZE}",
            )

            for post in info["posts"]:
                yield self._url_entry_from_post(post)

        return OnDemandPagedList(fetch_page, self.PAGE_SIZE)

    def _entries_from_blocks(self, blocks: Sequence[AnyDict]) -> Iterator[AnyDict]:
        """return url results or multiple playlists"""
        categories: Dict[str, AnyDict] = {}

        def flatten(_blocks: Sequence[AnyDict], depth=0):
            for _block in _blocks:
                post = _block.get("post", {})
                if "/v/" in post.get("link", ""):
                    category = post.get("stv_category_name")
                    entries = categories.setdefault(str(category), {})
                    entry = self._url_entry_from_post(
                        post, url_transparent=True, _block=category
                    )
                    entries[entry["id"]] = entry
                flatten(_block.get("innerBlocks", ()), depth=depth + 1)

        flatten(blocks)
        if len(categories) == 1:
            yield from categories.popitem()[1].values()
        else:
            for name, entry_map in categories.items():
                info = self.playlist_result(
                    list(entry_map.values()),
                    playlist_id=name.lower().replace(" ", "_"),
                    playlist_title=name,
                    extractor=self.IE_NAME,
                    extractor_key=self.ie_key(),
                )
                yield info

    @staticmethod
    def _page_data(json_obj: AnyDict) -> AnyDict:
        for item in ("data", "post", "page"):
            page_data = traverse_obj(
                json_obj, f"props/pageProps/{item}".split("/"), default={}
            )
            if page_data:
                break
        return page_data

    def _filter_query(self, json_obj: AnyDict, *names: str) -> Tuple[str, AnyDict]:
        data = traverse_obj(
            json_obj,
            "props/pageProps/initialLibData".split("/"),
            "props/pageProps/data".split("/"),
            default={},
        )
        for filter_info in data.get("filters", ()):
            name = filter_info.get("value", "none")
            if name in names:
                return name, filter_info

        return "none", {}

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
        if "/v/" in url_parts.path or url_parts.path.startswith("/videos/"):
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

        page_data = self._page_data(json_obj)

        # find livestreams
        live_schedule = page_data.get("stv_live_player_schedule")
        if live_schedule:
            return self._live_stream_from_schedule(
                live_schedule, page_data.get("stv_linear_stream_id")
            )

        # create playlist from query
        qid, filter_info = self._filter_query(json_obj, "all-videos", "upcoming")
        if filter_info:
            return self.playlist_result(
                self._paged_playlist_by_query(filter_info["url"], qid=qid),
                **self._playlist_meta(page_data, webpage),
                playlist_count=filter_info.get("count", "N/A"),
            )

        # create playlist from block data
        embedded_video = page_data.get("stv_embedded_video")
        entries = [self._url_entry_from_post(embedded_video)] if embedded_video else []
        entries.extend(self._entries_from_blocks(page_data.get("blocks", ())))
        if not entries:
            raise UnsupportedError(url)

        return self.playlist_result(
            entries,
            **self._playlist_meta(page_data, webpage),
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
                "id": "search_hubert+staller",
                "title": "search: 'hubert staller'",
                "description": None,
            },
            "params": {"skip_download": True, "geo_bypass": False},
            "playlist_mincount": 1,
            "playlist_maxcount": 10,
        }
    ]

    def _playlist_meta(self, page_data, webpage):
        search_term = page_data.get("searchTerm", "[searchTerm]")

        return {
            "playlist_id": f"search_{quote_plus(search_term)}",
            "playlist_title": f"search: {search_term!r}",
        }


class PmWissenIE(ServusTVIE):
    IE_NAME = "pm-wissen"
    _VALID_URL = r"""(?x)
                    https?://
                        (?:www\.)?(?:pm-wissen)\.com/
                        (?:
                            videos | (?: [\w-]+/(?: v | [p]/[\w-]+ ) )
                        )
                        /(?P<id>[A-Za-z0-9-]+)
                    """
    _TESTS = [
        {
            # test embedded links from 3rd party sites
            "url": "https://www.pm-wissen.com/umwelt/v/aa-24mus4g2w2112/",
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
            "params": {"skip_download": True, "format": "bestvideo"},
        },
        {
            # topic playlist
            "url": "https://www.pm-wissen.com/mediathek/p/redewendungen-mediathek/11908/",
            "info_dict": {
                "id": "redewendungen-mediathek",
                "title": "Redewendungen Mediathek",
                "description": "Alle Videos zum Thema Redewendungen",
            },
            "playlist_mincount": 20,
            "params": {"skip_download": True},
        },
        {
            # playlist from blocks (fails on older yt-dlp versions)
            "url": "https://www.pm-wissen.com/mediathek/p/highlights-mediathek/11900/",
            "info_dict": {
                "id": "highlights-mediathek",
                "title": "Mediathek",
                "description": "md5:2260ac68a6ee376912beb4c73e3d5b33",
            },
            "playlist_mincount": 12,
            "params": {"skip_download": True},
        },
    ]
    JSON_OBJ_ID = "__FRONTITY_CONNECT_STATE__"

    @staticmethod
    def _page_data(json_obj):
        for item in ("page", "data"):
            page_data = traverse_obj(json_obj, f"source/{item}".split("/"), default={})
            if page_data:
                page_data = next(iter(page_data.values()))
                break

        return page_data

    def _filter_query(self, json_obj, *names: str) -> Tuple[str, Dict]:
        link = traverse_obj(json_obj, ("router", "link"), default="")
        data = traverse_obj(
            json_obj,
            ("source", "data", link),
            default={},
        )
        for filter_info in data.get("filters", ()):
            name = filter_info.get("value", "none")
            if name in names:
                return name, filter_info

        page_data = self._page_data(json_obj)
        category = page_data.get("categories", ())
        if category:
            return category[0], {
                "url": "https://backend.pm-wissen.com/wp-json/rbmh/v2/query-filters/query/?"
                f"categories={category[0]}&f[primary_type_group]=all-videos&filter_bundles=true&"
                "filter_non_visible_types=true&geo_override=DE&orderby=rbmh_playability&"
                "page=3&per_page=12&post_type=media_asset&query_filters=primary_type_group"
            }

        return "none", {}


class PmWissenSearchIE(PmWissenIE):
    IE_NAME = "pm-wissen:search"
    _VALID_URL = r"""(?x)
                    https?://
                        (?:www\.)?pm-wissen.com
                        /search
                        /(?P<id>[^/?#]+)
                        (?:/all-videos/\d+)?/?$
                    """
    _TESTS = [
        {
            # search playlist
            "url": "https://www.pm-wissen.com/search/weltall/",
            "info_dict": {
                "id": "search_weltall",
                "title": "search: 'weltall'",
            },
            "params": {"skip_download": True, "geo_bypass": False},
            "playlist_mincount": 21,
        }
    ]

    def _playlist_meta(self, page_data, webpage):
        search_query = page_data.get("searchQuery", "[searchQuery]")

        return {
            "playlist_id": f"search_{quote_plus(search_query)}",
            "playlist_title": f"search: {search_query!r}",
        }

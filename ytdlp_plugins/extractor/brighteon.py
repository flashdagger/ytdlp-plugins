# coding: utf-8
import re
from contextlib import suppress
from sys import maxsize
from urllib.parse import parse_qs, urlencode, urlparse, urlunparse

from yt_dlp.extractor.common import InfoExtractor
from yt_dlp.utils import (
    ExtractorError,
    OnDemandPagedList,
    UnsupportedError,
    clean_html,
    get_element_by_id,
    int_or_none,
    parse_duration,
    parse_iso8601,
    traverse_obj,
    update_url_query,
    urljoin,
)
from ytdlp_plugins.probe import headprobe_media
from ytdlp_plugins.utils import ParsedURL

__version__ = "2022.10.13.post1"


# pylint: disable=abstract-method
class BrighteonIE(InfoExtractor):
    IE_NAME = "brighteon"
    _VALID_URL = r"""(?x)
                    https?://
                        (?:www\.)?
                        (?:brighteon\.com/)
                        (?:(?P<taxonomy>browse|channels|categories|watch)/)?
                        (?P<id>[a-zA-z0-9-]+)
                    """
    _EMBED_URL_RE = (
        re.compile(
            r"""(?x)
                <iframe[^>]+src="
                (?P<url>https?://(?:[a-z][\da-z]+\.)?
                brighteon\.com/embed/[\da-zA-Z-]+)
                [^"]*"
            """
        ),
    )
    _BASE_URL = "https://www.brighteon.com"
    _MPEG_TS = True

    _TESTS = [
        {
            "url": "https://www.brighteon.com/4f2586ec-66ac-4db7-ac72-efb5f0473406",
            "md5": "9a6a3ce5c3391eccb71f995f530209d5",
            "info_dict": {
                "id": "4f2586ec-66ac-4db7-ac72-efb5f0473406",
                "title": "10/26/2022 Let's Talk America: Dr. Alan Keyes ft. Dennis Pyle",
                "ext": "mp3",
                "description": 'Watch "Let\'s Talk America" Live on Brighteon.tv '
                "every weekday from 2:00 pm - 3:00 pm estSupport "
                "Let's Talk America by visiting or donating at https://iamtv.us/",
                "timestamp": 1666814967,
                "upload_date": "20221026",
                "duration": 3033.0,
                "channel": "BrighteonTV",
                "channel_id": "123538c1-de87-46d0-a0ad-be8efebbfaa1",
                "channel_url": "https://www.brighteon.com/channels/brighteontv",
                "tags": [
                    "current events",
                    "bible",
                    "declaration of independence",
                    "scripture",
                    "american politics",
                    "constitutional rights",
                    "conservative patriot",
                    "lets talk america",
                    "dr alan keyes",
                ],
                "thumbnail": "re:https?://[a-z]+.brighteon.com/(?:[a-z-]+/)+[a-f0-9-]+",
                "view_count": int,
                "like_count": int,
            },
            "params": {"check_formats": False, "format": "audio"},
        },
        {
            # playlist
            "url": "https://www.brighteon.com/watch/21824dea-3564-40af-a972-d014b987261b",
            "info_dict": {
                "id": "21824dea-3564-40af-a972-d014b987261b",
                "title": "U.S. Senate Impeachment Trial",
            },
            "playlist_mincount": 10,
        },
        {
            # channel
            "url": "https://www.brighteon.com/channels/brighteontv",
            "info_dict": {
                "id": "123538c1-de87-46d0-a0ad-be8efebbfaa1",
                "title": "BrighteonTV",
            },
            "playlist_mincount": 50,
        },
        {
            # categories
            "url": "https://www.brighteon.com/categories/"
            "4ad59df9-25ce-424d-8ac4-4f92d58322b9/videos",
            "info_dict": {
                "id": "4ad59df9-25ce-424d-8ac4-4f92d58322b9",
                "title": "Health & Medicine",
            },
            "playlist_mincount": 50,
        },
        {
            # browse
            "url": "https://www.brighteon.com/browse/new-videos",
            "info_dict": {
                "id": "new-videos",
                "title": "new-videos",
            },
            "playlist_mincount": 50,
        },
        {
            # test embedded urls
            "url": "https://healthfreedom.news/2020-05-20-plandemic-video-super-viral-brighteon-"
            "facebook-banning-cleansing-content-wuhan-coronavirus.html",
            "info_dict": {
                "id": "2020-05-20-plandemic-video-super-viral-brighteon-facebook-banning-"
                "cleansing-content-wuhan-coronavirus",
                "title": "After “Plandemic” video goes super viral on Brighteon.com, "
                "Facebook bans all Brighteon links, regardless of content",
                "description": str,
                "timestamp": (int, float),
                "upload_date": str,
            },
            "playlist_mincount": 1,
            "playlist": [
                {
                    "md5": "66c73716a5cf4299cb9c7ba9969b11ff",
                    "info_dict": {
                        "id": "45c1558c-4163-4961-9f92-11c7c4c1af21",
                        "title": "PlanDEMIC - Jesus Social Edition",
                        "ext": "mp4",
                        "description": str,
                        "timestamp": int,
                        "upload_date": str,
                    },
                }
            ],
        },
    ]

    @staticmethod
    def page_props_path(suffix=None):
        path = ["props", "initialProps", "pageProps"]
        if suffix:
            path.extend(suffix.split("."))
        return path

    def _json_api(self, url, video_id, **kwargs):
        parsed_url = urlparse(url)
        parsed_qs = parse_qs(parsed_url.query)
        path = parsed_url.path.rstrip("/")

        if path.startswith("/channels/") and path.endswith("/videos"):
            path = path.replace("/videos", "/")
        if path.startswith("/categories/") and not path.endswith("/videos"):
            path = path + "/videos"

        # noinspection PyProtectedMember
        json_api_url = urlunparse(
            parsed_url._replace(path="/api-v3" + path, query=urlencode(parsed_qs, True))
        )
        json_obj = self._download_json(json_api_url, video_id=video_id, **kwargs)
        return json_obj

    def _json_extract(self, url, video_id, note=None):
        webpage = self._download_webpage(url, video_id=video_id, note=note)
        try:
            return self._parse_json(
                get_element_by_id("__NEXT_DATA__", webpage), video_id=video_id
            )
        except TypeError as exc:
            raise ExtractorError(
                "Could not extract JSON metadata", video_id=video_id
            ) from exc

    @staticmethod
    def _rename_formats(formats, prefix):
        for item in formats:
            if "vcodec" in item and item["vcodec"] == "none":
                language = item.get("language")
                suffix = f"audio-{language}" if language else "audio"
            else:
                suffix = (
                    f'{item["height"]}p' if item.get("height") else item["format_id"]
                )
            item["format_id"] = f"{prefix}-{suffix}"

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

    def _download_formats(self, sources, video_id):
        formats = []
        if not sources:
            return formats

        for source in sources:
            try:
                url = source["src"]
                typ = source.get("type", url[-3:])
            except KeyError:
                continue
            if url.endswith(".m3u8"):
                media_formats = self._extract_m3u8_formats(
                    url, video_id=video_id, fatal=False
                )
                self._rename_formats(media_formats, "hls")

                if self._MPEG_TS:
                    mpg_formats = []
                    for fmt in media_formats:
                        mpg_fmt = {
                            key: value
                            for key, value in fmt.items()
                            if key not in {"url", "manifest_url", "protocol"}
                        }
                        mpg_fmt["url"] = fmt["url"].replace(".m3u8", ".ts")
                        mpg_formats.append(mpg_fmt)
                    self._rename_formats(mpg_formats, "mpeg")
                    media_formats.extend(mpg_formats)
            elif url.endswith(".mpd"):
                media_formats = self._extract_mpd_formats(
                    url, video_id=video_id, fatal=False
                )
                self._rename_formats(media_formats, "dash")
                for fmt in media_formats:
                    fmt["manifest_stream_number"] = 0
            else:
                media_formats = ()
                self.report_warning(f"unknown media format {typ!r}")
            formats.extend(media_formats)

        for fmt in formats:
            fps = fmt.get("fps")
            fmt["fps"] = fps and round(fps)

        return formats

    def _update_formats(self, formats):
        for fmt in formats:
            if fmt.get("height"):
                fmt["fps"] = 30 if fmt["height"] >= 540 else 15
            if self.get_param("check_formats") is False or not (
                fmt.get("format_note", "").startswith("DASH video")
            ):
                continue
            info = headprobe_media(self, fmt["url"])[0]
            fmt.update(info)

    def _entry_from_info(self, video_info, channel_info, from_playlist=False):
        video_id = video_info["id"]
        url = f"{self._BASE_URL}/{video_id}"
        duration = parse_duration(video_info.get("duration"))

        if from_playlist:
            _type = "url"
            formats = None
        else:
            _type = "video"
            formats = self._download_formats(
                video_info.get("source", ()), video_id=video_id
            )
            if video_info.get("audio"):
                formats.append(
                    {
                        "format_id": "audio",
                        "url": video_info["audio"],
                        "vcodec": "none",
                        "acodec": "aac",
                        "tbr": 192,  # estimation for filesize_approx
                        "asr": 48000,
                    }
                )
            self._update_formats(formats)
            self._sort_formats(formats)
            self._auto_merge_formats(formats)

        # merge channel_info items into video_info
        for item in ("name", "id", "shortUrl"):
            channel_item = channel_info.get(item)
            if channel_item:
                ci_name = f"channel{item[0].upper()}{item[1:]}"
                video_info[ci_name] = channel_item

        entry_info = {
            "_type": _type,
            "url": url,
            "id": video_id,
            "title": video_info.get("name"),
            "description": clean_html(video_info.get("description")),
            "timestamp": parse_iso8601(video_info.get("createdAt")),
            "duration": duration,
            "channel": video_info.get("channelName"),
            "channel_id": video_info.get("channelId"),
            "channel_url": video_info.get("channelShortUrl")
            and f'{self._BASE_URL}/channels/{video_info["channelShortUrl"]}',
            "tags": video_info.get("tags", []),
            "thumbnail": video_info.get("thumbnail"),
            "view_count": traverse_obj(
                video_info, ("analytics", "videoView"), default=None
            ),
            "like_count": int_or_none(video_info.get("likes")),
        }
        if formats is not None:
            entry_info["formats"] = formats

        return entry_info

    def _paged_url_entries(self, page_id, url, start_page=None, use_json_api=True):
        max_pages = None

        def load_page(page_number):
            page_url = update_url_query(url, {"page": page_number})
            note = f"Downloading page {page_number}"
            if max_pages:
                note = f"{note}/{max_pages}"

            if use_json_api:
                return self._json_api(page_url, video_id=page_id, note=note)

            json_obj = self._json_extract(page_url, video_id=page_id, note=note)
            page_props = traverse_obj(json_obj, self.page_props_path(), default={})
            return page_props.get("data") or page_props

        data = load_page(start_page or "1")
        channel_info = data.get("channel", {})
        initial_video_list = data.get("videos")
        if initial_video_list is None:
            raise UnsupportedError(url)
        page_cache = {1: initial_video_list}
        page_size = len(initial_video_list)
        pagination = data.get("pagination", data)
        max_pages = pagination.get("pages", maxsize)

        def fetch_entry(index):
            page_idx, offset = divmod(index, page_size)
            page_number = page_idx + 1

            if (
                start_page is None
                and page_number not in page_cache
                and page_number <= max_pages
            ):
                video_list = load_page(page_number).get("videos", ())
                page_cache.clear()  # since we only need one entry
                page_cache[page_number] = video_list
            else:
                video_list = page_cache.get(page_number, ())

            with suppress(IndexError):
                yield self._entry_from_info(
                    video_list[offset], channel_info, from_playlist=True
                )

        playlist_info = channel_info or data
        return self.playlist_result(
            entries=OnDemandPagedList(fetch_entry, 1),
            playlist_id=playlist_info.get("id", page_id),
            playlist_title=playlist_info.get("name", page_id),
            playlist_count=page_size if start_page else pagination.get("count", "N/A"),
        )

    def _playlist_entries(self, playlist_info, url):
        entries = []
        for idx, video in enumerate(playlist_info.get("videosInPlaylist", ()), 1):
            entries.append(
                {
                    "_type": "url",
                    "url": update_url_query(url, {"index": idx}),
                    "title": video.get("videoName"),
                    "duration": parse_duration(video.get("duration")),
                }
            )
        return self.playlist_result(
            entries=entries,
            playlist_id=playlist_info.get("playlistId"),
            playlist_title=playlist_info.get("playlistName"),
            playlist_count=len(entries),
        )

    def _real_extract(self, url):
        match = self._match_valid_url(url)
        taxonomy, video_id = match.groups()
        parsed_url = ParsedURL(url)
        self._set_cookie("brighteon.com", "adBlockClosed", "1")

        if taxonomy in {"channels", "categories", "browse"}:
            return self._paged_url_entries(
                video_id,
                url,
                start_page=parsed_url.query("page"),
                use_json_api=taxonomy != "browse",
            )

        json_obj = self._json_extract(url, video_id=video_id)
        page_props = traverse_obj(json_obj, self.page_props_path(), default={})

        playlist_info = page_props.get("playlist", {})
        if playlist_info and parsed_url.query("index") is None:
            return self._playlist_entries(playlist_info, url)

        video_info = page_props.get("video", {})
        channel_info = page_props.get("channel", {})
        if video_info:
            return self._entry_from_info(video_info, channel_info)

        raise UnsupportedError(url)


class BrighteonTvIE(BrighteonIE):
    IE_NAME = "brighteontv"
    _VALID_URL = r"""(?x)
                    https?://
                        (?:www\.)?
                        brighteon\.tv/?
                    """

    _BASE_URL = "https://www.brighteon.tv"
    _MPEG_TS = False

    _TESTS = [
        {
            "url": "https://www.brighteon.tv/LiveTV/",
            "info_dict": {
                "id": "brighteontv-daily-show",
                "ext": "mp4",
                "title": "startswith:Brighteon.TV Daily Show",
                "description": str,
                "channel_id": "8c536b2f-e9a1-4e4c-a422-3867d0e472e4",
                "tags": [
                    "Brighteon.TV",
                    "Video",
                    "Live",
                    "Streaming",
                    "Shows",
                    "Events",
                    "Documentaries",
                ],
                "is_live": True,
            },
            "params": {"skip_download": True},
        },
        {
            "url": "https://www.brighteon.tv/LiveEspanol/",
            "info_dict": {
                "id": "brighteontv-espanol",
                "ext": "mp4",
                "title": "startswith:Brighteon.TV Espanol",
                "description": str,
                "channel_id": "8c536b2f-e9a1-4e4c-a422-3867d0e472e4",
                "tags": [
                    "Brighteon.TV",
                    "Video",
                    "Live",
                    "Streaming",
                    "Shows",
                    "Events",
                    "Documentaries",
                ],
                "is_live": True,
            },
            "params": {"skip_download": True},
        },
        {
            "url": "https://www.brighteon.tv/LiveEvents/",
            "info_dict": {
                "id": "brighteon2-show",
                "ext": "mp4",
                "title": "startswith:Brighteon.TV Daily Show",
                "description": str,
                "channel_id": "8c536b2f-e9a1-4e4c-a422-3867d0e472e4",
                "tags": [
                    "Brighteon.TV",
                    "Video",
                    "Live",
                    "Streaming",
                    "Shows",
                    "Events",
                    "Documentaries",
                ],
                "is_live": True,
            },
            "params": {"skip_download": True},
        },
    ]

    def _real_extract(self, url):
        video_id = self.ie_key()
        webpage = self._download_webpage(url, video_id=video_id)
        description = self._og_search_description(webpage)
        tags = self._html_search_meta("keywords", webpage, default="")
        stream_url = self._search_regex(
            r'<iframe[^>]+src="(https?://[\w./-]+)"', webpage, "stream_url", fatal=False
        )
        if stream_url is None:
            raise UnsupportedError(url)
        json_obj = self._json_extract(stream_url, video_id=video_id)
        stream_info = traverse_obj(json_obj, self.page_props_path("stream"))
        video_info = self._entry_from_info(stream_info, {})
        video_info.update(
            dict(description=description, tags=tags.split(", "), is_live=True)
        )

        return video_info


class BrighteonRadioIE(BrighteonIE):
    IE_NAME = "brighteonradio"
    _VALID_URL = r"(?P<base>https?://(?:www\.)?brighteonradio\.com)/?"
    _BASE_URL = "https://www.brighteonradio.com"
    _MPEG_TS = False

    _TESTS = [
        {
            "url": "https://www.brighteonradio.com/",
            "info_dict": {
                "id": "BrighteonRadio",
                "ext": "mp4",
                "title": "startswith:Brighteon Radio",
                "description": "Free Speech Audio Streaming for Humanity",
                "tags": ["Brighteon", "Radio", "News", "Audio", "Streaming"],
                "is_live": True,
            },
            "params": {"skip_download": True},
        },
    ]

    def _real_extract(self, url):
        video_id = self.ie_key()
        webpage = self._download_webpage(url, video_id=video_id)
        player_url = self._search_regex(
            r'<script[^>]+src="([^"]+/Player\w*.js)"', webpage, "player_url"
        )
        player_js = self._download_webpage(
            urljoin(self._BASE_URL, player_url),
            note="Downloading JS player",
            video_id=video_id,
        )
        stream_url = self._search_regex(
            r"^\s*var\s+[^'\"/]+['\"](https?://[^'\"]+/index\.m3u8)['\"]",
            player_js,
            "stream_url",
            flags=re.MULTILINE,
        )
        formats = self._extract_m3u8_formats(stream_url, video_id)
        for fmt in formats:
            fmt["height"] = fmt["width"] = None
            fmt["vcodec"] = "none"
        self._sort_formats(formats)
        ffmpeg_args = self.get_param("external_downloader_args")
        if isinstance(ffmpeg_args, dict):
            ffmpeg_args.setdefault("ffmpeg_o", []).append("-vn")

        tags = [
            tag.strip()
            for tag in self._html_search_meta("keywords", webpage, default="").split(
                ","
            )
        ]

        return {
            "id": video_id,
            "title": self._og_search_title(webpage, default="Brighteon Radio"),
            "description": self._og_search_description(webpage),
            "tags": tags,
            "is_live": True,
            "formats": formats,
        }

#!/usr/bin/python3
# -*- coding: utf-8 -*-

import json
import re
from datetime import datetime, timedelta
from itertools import count
from urllib.parse import unquote_plus

from yt_dlp.extractor.common import InfoExtractor
from yt_dlp.utils import (
    ExtractorError,
    LazyList,
    OnDemandPagedList,
    float_or_none,
    int_or_none,
    parse_duration,
    parse_iso8601,
    traverse_obj,
    update_url_query,
)
from ytdlp_plugins.probe import probe_media

__version__ = "2023.12.27"


# pylint: disable=abstract-method
class DTubePluginIE(InfoExtractor):
    _VALID_URL = r"""(?x)
                    https?://(?:www\.)?d\.tube/
                    (?:\#!/)?v/
                    (?P<id>[0-9a-z.-]+/[\w-]+)
                    """
    IE_NAME = "d.tube"

    GATEWAY_URLS = {
        "ipfs": [
            "https://player.d.tube/ipfs",
            "https://ipfs.d.tube/ipfs",
            "https://ipfs.io/ipfs",
        ],
        "btfs": ["https://player.d.tube/btfs", "https://btfs.d.tube/btfs"],
        "sia": ["https://siasky.net"],
    }

    REDIRECT_TEMPLATES = {
        "vimeo": "https://vimeo.com/{}",
        "twitch": "https://www.twitch.tv/{}",
        "youtube": "{}",
        "facebook": "https://www.facebook.com/video.php?v={}",
        "dailymotion": "https://www.dailymotion.com/video/{}",
    }

    # pylint: disable=line-too-long
    _TESTS = [
        {
            "url": "https://d.tube/v/truehnchannel3.0/QmNXrihTWmHiLVXxLabfXFakFzJVLq1LimfH2X1sNma5ak",
            "skip": "not available",
            "md5": "d7b147de74210442e6b14d934f96c585",
            "info_dict": {
                "id": "truehnchannel3.0/QmNXrihTWmHiLVXxLabfXFakFzJVLq1LimfH2X1sNma5ak",
                "title": "HAPPY WEEKEND #TRUEHNERS #TRUEHNER FROM THE TEAM OF TRUE_HUMANNATURE - THE TRUEHN BACKED FASHION & BEAUTY BRAND ",
                "description": "md5:452385a9aef03447baa2aae9c801eb14",
                "ext": "mp4",
                "thumbnail": "https://ipfs.io/ipfs/QmcFBCAx8c8PLew7JfjVmn3VK6MjrSMfCerq5b5y9iNdp8?filename=AAAAAAAAAAA%20TRUEHUMAN%20NATURE.jpg",
                "tags": ["truehnchannel"],
                "duration": 3,
                "uploader_id": "truehnchannel3.0",
                "upload_date": "20230603",
                "timestamp": 1685782622.873,
            },
            "params": {
                "format": "src",
            },
        },
        {
            # using avalon API
            "url": "https://d.tube/#!/v/cahlen/desert-fire",
            "md5": "f3d0df537692c2cd725231cebdbd8e7e",
            "info_dict": {
                "id": "cahlen/desert-fire",
                "title": "Desert Fire",
                "description": "md5:e61b355bc49e480b1a8e7a3f5406edbd",
                "ext": "mp4",
                "tags": ["life"],
                "duration": 151,
                "uploader_id": "cahlen",
                "upload_date": "20231217",
                "timestamp": 1702856641.012,
            },
            "params": {
                "format": "src",
            },
            "expected_warnings": ["Unable to download avalon metadata"],
        },
        # dailymotion forward
        {
            "url": "https://d.tube/#!/v/charliesmithmusic11/cup890u4sra",
            "info_dict": {
                "id": "x86k2uu",
                "title": str,
                "description": str,
                "ext": str,
                "uploader": str,
                "uploader_id": str,
                "upload_date": str,
                "timestamp": (int, float),
                "extractor": "dailymotion",
            },
            "params": {
                "skip_download": True,
            },
        },
        # YouTube forward
        {
            "url": "https://d.tube/#!/v/geneeverett33/74w7hgkthww",
            "info_dict": {
                "id": "rmFZqbh7TaU",
                "title": str,
                "description": str,
                "ext": str,
                "uploader": str,
                "uploader_id": str,
                "upload_date": str,
                "extractor": "youtube",
            },
            "params": {
                "skip_download": True,
            },
        },
    ]

    def formats(self, files):
        # pylint: disable=undefined-loop-variable
        for provider, default_gateways in self.GATEWAY_URLS.items():
            if provider in files and "vid" in files[provider]:
                break
        else:
            return []

        gateway = files[provider].get("gw", "").rstrip("/")
        if gateway and not re.match(r".*/(?:btfs|ipfs)$", gateway):
            gateway = f"{gateway}/{provider}"

        if gateway in default_gateways:
            default_gateways.remove(gateway)
            default_gateways.insert(0, gateway)

        loop_gateways = list(default_gateways)
        if gateway and gateway not in loop_gateways:
            loop_gateways.insert(0, gateway)

        formats = []
        for format_id, content_id in sorted(files[provider].get("vid", {}).items()):
            for gateway in list(loop_gateways):
                self.write_debug(f"checking media via gateway {gateway!r}")
                media_url = f"{gateway}/{content_id}"
                probed_format, *_ = probe_media(self, media_url)
                if "filesize" in probed_format:
                    media_format = {**probed_format, "format_id": format_id}
                    break
                loop_gateways.remove(gateway)
            else:
                media_format = None

            if media_format:
                formats.append(media_format)

        return formats

    @staticmethod
    def fallback_files(info):
        files = {}
        for provider in ("ipfs", "btfs"):
            provider_info = info.get(provider, {})
            for key, value in provider_info.items():
                match = re.match(r"video(\d*)hash", key)
                if match is None:
                    continue
                resolution = match.group(1) or "src"
                files.setdefault(provider, {}).setdefault("vid", {})[resolution] = value
        return files

    def avalon_api(self, endpoint, video_id, **kwargs):
        options = {
            "note": "Downloading avalon metadata",
            "errnote": "Unable to download avalon metadata",
            "fatal": False,
        }
        options.update(kwargs)
        result = self._download_json(
            f"https://avalon.d.tube/{endpoint}",
            video_id,
            **options,
        )

        return result

    def steemit_api(self, video_id):
        data = {
            "id": 0,
            "jsonrpc": "2.0",
            "method": "call",
            "params": ["condenser_api", "get_state", [f"/dtube/@{video_id}"]],
        }
        result = self._download_json(
            "https://api.steemit.com/",
            video_id,
            headers={"Content-Type": "application/json"},
            data=json.dumps(data).encode("utf-8"),
            note="Downloading steemit metadata",
        )

        content = traverse_obj(result, ("result", "content", video_id), default={})
        metadata = json.loads(content.get("json_metadata", "{}"))
        if not metadata.get("video"):
            raise ExtractorError(
                "Steemit metadata not availabe", video_id=video_id, expected=True
            )

        return {
            "_id": video_id,
            "author": content.get("author"),
            "link": content.get("permlink"),
            "json": metadata.get("video", {}),
            "ts": (parse_iso8601(content.get("last_update")) or 0) * 1000,
            "tags": dict.fromkeys(metadata.get("tags", ()), 0),
        }

    def entry_from_avalon_result(self, result, from_playlist=False):
        video_id = f"{result['author']}/{result['link']}"
        info = result["json"]
        video_provider = info.get("files", {})
        redirect_ies = set(self.REDIRECT_TEMPLATES.keys()) & set(video_provider.keys())
        if redirect_ies:
            redirect_ie = redirect_ies.pop()
            redirect_url = self.REDIRECT_TEMPLATES[redirect_ie].format(
                video_provider[redirect_ie]
            )
        elif "url" in info:
            redirect_url = info["url"]
        else:
            redirect_url = None

        if from_playlist or redirect_url:
            _type = "url"
            formats = None
        else:
            _type = "video"
            formats = self.formats(info.get("files", self.fallback_files(info)))

        tags = result.get("tags")
        if tags:
            tags = list(tags.keys()) if isinstance(tags, dict) else [tags]
        else:
            tags = []

        entry_info = {
            "_type": _type,
            "url": redirect_url or f"https://d.tube/v/{video_id}",
            "id": video_id,
            "title": traverse_obj(info, ("title",), ("info", "title")),
            "description": traverse_obj(
                info, ("desc",), ("description",), ("content", "description")
            ),
            "thumbnail": info.get("thumbnailUrl"),
            "tags": tags,
            "duration": float_or_none(
                traverse_obj(info, ("duration",), ("info", "duration"))
            )
            or int_or_none(info.get("dur"))
            or parse_duration(info.get("dur")),
            "timestamp": float_or_none(result.get("ts"), scale=1000),
            "uploader_id": result.get("author"),
        }

        if formats is not None:
            entry_info["formats"] = formats

        return entry_info

    def _real_extract(self, url):
        video_id = self._match_id(url)
        result = self.avalon_api(f"content/{video_id}", video_id)
        if not result:
            result = self.steemit_api(video_id)

        return self.entry_from_avalon_result(result)


class DTubeUserPluginIE(DTubePluginIE):
    _VALID_URL = r"""(?x)
                    https?://(?:www\.)?d\.tube/
                    (?:\#!/)?c/
                    (?P<id>[0-9a-z.-]+)
                    """
    IE_NAME = "d.tube:user"

    _TESTS = [
        {
            "url": "https://d.tube/#!/c/cahlen",
            "playlist_mincount": 100,  # type: ignore
            "info_dict": {
                "id": "cahlen",
                "title": "cahlen",
            },
        },
    ]

    def iter_entries(self, user_id, endpoint):
        page_size = 50
        last_id = None

        for page in count(1):
            result = self.avalon_api(
                f"{endpoint}/{last_id}" if last_id else endpoint,
                user_id,
                note=f"Downloading page {page}",
            )
            start_idx = 1 if result and result[0]["_id"] == last_id else 0

            for item in result[start_idx:]:
                yield self.entry_from_avalon_result(item, from_playlist=True)

            if len(result) < page_size:
                return
            if result:
                last_id = result[-1]["_id"]

    def _real_extract(self, url):
        user_id = self._match_id(url)
        endpoint = f"blog/{user_id}"

        return self.playlist_result(
            LazyList(self.iter_entries(user_id, endpoint)),
            playlist_id=user_id,
            playlist_title=user_id,
        )


class DTubeQueryPluginIE(DTubeUserPluginIE):
    _VALID_URL = r"""(?x)
                    https?://(?:www\.)?d\.tube/
                    (?:\#!/)?
                    (?P<id>hotvideos|trendingvideos|newvideos)
                    """
    IE_NAME = "d.tube:query"

    _TESTS = [
        {
            "url": "https://d.tube/#!/hotvideos",
            "playlist_mincount": 80,  # type: ignore
            "info_dict": {
                "id": "hotvideos",
                "title": "hotvideos",
            },
        },
        {
            "url": "https://d.tube/trendingvideos",
            "playlist_mincount": 50,  # type: ignore
            "info_dict": {
                "id": "trendingvideos",
                "title": "trendingvideos",
            },
        },
        {
            "url": "https://d.tube/newvideos",
            "playlist_mincount": 50,  # type: ignore
            "info_dict": {
                "id": "newvideos",
                "title": "newvideos",
            },
        },
    ]

    def _real_extract(self, url):
        query_id = self._match_id(url)
        assert query_id.endswith("videos")
        endpoint = query_id[: -len("videos")]

        return self.playlist_result(
            LazyList(self.iter_entries(query_id, endpoint)),
            playlist_id=query_id,
            playlist_title=query_id,
        )


class DTubeSearchPluginIE(DTubePluginIE):
    _VALID_URL = r"""(?x)
                    https?://(?:www\.)?d\.tube/
                    (?:\#!/)?[st]/
                    (?P<id>[^?]+)
                    """
    IE_NAME = "d.tube:search"

    _TESTS = [
        {
            "url": "https://d.tube/#!/s/crypto+currency",
            "playlist_mincount": 60,  # type: ignore
            "info_dict": {
                "id": "crypto+currency",
                "title": "crypto currency",
            },
        },
        {
            "url": "https://d.tube/t/gaming",
            "playlist_mincount": 20,  # type: ignore
            "info_dict": {
                "id": "gaming",
                "title": "gaming",
            },
        },
    ]

    def _real_extract(self, url):
        page_size = 30
        search_term_quoted = self._match_id(url)
        search_term = unquote_plus(search_term_quoted)

        if "/t/" in url:
            # tag search
            timestamp = int((datetime.now() - timedelta(weeks=52)).timestamp() * 1e3)
            payload = {
                "q": f"(NOT pa:*) AND ts:>={timestamp} AND tags:{search_term}",
                "sort": "ups:desc",
            }
        else:
            # common search
            payload = {"q": f"(NOT pa:*) AND {search_term}"}

        def fetch_page(page_number):
            offset = page_number * page_size
            result = self._download_json(
                update_url_query(
                    "https://search.d.tube/avalon.contents/_search",
                    {**payload, "size": page_size, "from": offset},
                ),
                search_term,
                note=f"Downloading entries from offset {offset:3}",
                fatal=False,
            )
            if not result:
                return
            for hit in traverse_obj(result, ["hits", "hits"], default=()):
                yield self.entry_from_avalon_result(hit["_source"], from_playlist=True)

        return self.playlist_result(
            OnDemandPagedList(fetch_page, page_size),
            playlist_id=search_term_quoted,
            playlist_title=search_term,
        )

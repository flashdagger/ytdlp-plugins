# coding: utf-8
import json
import re
from datetime import datetime, timedelta

from yt_dlp.compat import (
    compat_urllib_parse_unquote_plus,
)
from yt_dlp.extractor.common import InfoExtractor
from yt_dlp.postprocessor import FFmpegPostProcessor
from yt_dlp.utils import (
    ExtractorError,
    HEADRequest,
    LazyList,
    OnDemandPagedList,
    int_or_none,
    parse_duration,
    traverse_obj,
    update_url_query,
    float_or_none,
    parse_iso8601,
)

__version__ = "2022.01.02"


# pylint: disable=abstract-method
class DTubeIE(InfoExtractor):
    _VALID_URL = r"""(?x)
                    https?://(?:www\.)?d\.tube/
                    (?:\#!/)?v/
                    (?P<id>[0-9a-z.-]+/[\w-]+)
                    """
    IE_NAME = "d.tube"

    PROVIDER_URLS = {
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

    _TESTS = [
        {
            "url": "https://d.tube/v/famigliacurione/"
            "QmUJquzf7DALjwUExoHtTjS8PgGqfGohzMr4W3XJ56q9pR",
            "md5": "4ad5272197655dc033bfd0cc039b71f2",
            "info_dict": {
                "id": "famigliacurione/QmUJquzf7DALjwUExoHtTjS8PgGqfGohzMr4W3XJ56q9pR",
                "title": "La Prova by SOSO",
                "description": "md5:c942bfe98693a2e81510464d10869449",
                "ext": "mp4",
                "thumbnail": "https://cdn.steemitimages.com/"
                "DQmbCfaJkTRrjerNhcyDCoviBqpXB8ZDh31NhQPWvcyEj6U/laprovathumb.jpg",
                "tags": ["music", "hiphop"],
                "duration": 71,
                "uploader_id": "famigliacurione",
                "upload_date": "20211223",
                "timestamp": 1640297596.628,
            },
            "params": {
                "format": "480",
            },
        },
        # fallback files
        {
            "url": "https://d.tube/#!/v/reeta0119/QmX9rAqkTzYfUoi5VFuitzYQXyybFtURyUUWcYkyPXzkkz",
            "md5": "179f4435eb5068d3b1c6188ec3065d9a",
            "info_dict": {
                "id": "reeta0119/QmX9rAqkTzYfUoi5VFuitzYQXyybFtURyUUWcYkyPXzkkz",
                "title": "Splinterlands Battle Share Theme: DIVINE SORCERESS",
                "description": "md5:4521cc098e7dcad3e9a7f73095c9ffe9",
                "ext": "mp4",
                "thumbnail": "https://snap1.d.tube/ipfs/"
                "QmWYECptp7XKVEUk4tBf9R6d5XaRUo6Hcow6abtuy1Q3Vt",
                "duration": None,
                "uploader_id": "reeta0119",
                "upload_date": "20200306",
                "timestamp": 1583519894.482,
            },
            "params": {
                "format": "480",
            },
        },
        {
            # using steemit API
            "url": "https://d.tube/v/cahlen/hcyx513ospn",
            "md5": "fd03f59d2c1f7b1e0ed5a2098116e443",
            "info_dict": {
                "id": "cahlen/hcyx513ospn",
                "title": "Wizard's Life - February 20th, 2022",
                "description": "md5:4308b3aac098bf762489eeeea290b8e1",
                "ext": "mp4",
                "thumbnail": "https://ipfs.cahlen.org/ipfs/"
                "QmW9PQUeZAZZ2zryMp5kEVQqpKjJpHNGGUShmojcsW4zQZ",
                "tags": ["dtube", "life"],
                "duration": 1120,
                "uploader_id": "cahlen",
                "upload_date": "20220220",
                "timestamp": 1645382061.0,
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
            "url": "https://d.tube/#!/v/geneeverett33/jkp3e8v4tau",
            "info_dict": {
                "id": "InRmAxWpbOA",
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

    def __init__(self, downloader=None):
        super().__init__(downloader)
        self.ffmpeg = FFmpegPostProcessor(downloader)

    def ffprobe_format(self, media_url):
        # Invoking ffprobe to determine resolution
        self.to_screen("Checking format with ffprobe")
        timeout = self.get_param("socket_timeout")
        timeout = int(timeout * 1e6) if timeout else 2000000
        metadata = self.ffmpeg.get_metadata_object(
            media_url,
            opts=(
                "-timeout",
                str(timeout),
                "-headers",
                "referer: https://emb.d.tube/\r\n",
            ),
        )
        if not metadata:
            return None

        v_stream = {}
        a_stream = {}
        for stream in metadata["streams"]:
            if not v_stream and stream["codec_type"] == "video":
                v_stream.update(stream)
            elif not a_stream and stream["codec_type"] == "audio":
                a_stream.update(stream)

        extension_map = {
            "matroska": "mkv",
            "mp4": "mp4",
        }
        extensions = metadata["format"]["format_name"].split(",")
        for ext in extensions:
            if ext in extension_map:
                extension = extension_map[ext]
                break
        else:
            extension = extensions[0]

        fps = None
        if "r_frame_rate" in v_stream:
            match = re.match(r"(\d+)(?:/(\d+))?", v_stream["r_frame_rate"])
            if match:
                nom, den = match.groups()
                fps = round(int(nom) / int(den or 1))

        return {
            "url": media_url,
            "ext": extension,
            "container": extension,
            "vcodec": v_stream.get("codec_name"),
            "acodec": a_stream.get("codec_name"),
            "fps": fps,
            "asr": int_or_none(a_stream.get("sample_rate")),
            "tbr": int_or_none(metadata["format"].get("bit_rate"), scale=1000),
            "vbr": int_or_none(v_stream.get("bit_rate"), scale=1000) or 0,
            "abr": int_or_none(a_stream.get("bit_rate"), scale=1000) or 0,
            "height": int_or_none(v_stream.get("height")),
            "width": int_or_none(v_stream.get("width")),
            "filesize": int_or_none(metadata["format"].get("size")),
        }

    def http_format(self, media_url):
        try:
            head_response = self._request_webpage(
                HEADRequest(media_url),
                None,
                note="Checking format",
                headers={"referer": "https://emb.d.tube/"},
            )
        except ExtractorError:
            return None

        return {
            "url": media_url,
            "filesize": int_or_none(head_response.headers["Content-Length"]),
            "ext": head_response.headers["Content-Type"].split("/")[-1],
        }

    def formats(self, files):
        # pylint: disable=undefined-loop-variable
        for provider, base_urls in self.PROVIDER_URLS.items():
            if provider in files and "vid" in files[provider]:
                break
        else:
            return []

        formats = []
        media_format = {}
        candidate = files[provider].get("gw", "").rstrip("/")

        for format_id, content_id in sorted(files[provider].get("vid", {}).items()):
            if candidate in base_urls:
                base_urls.remove(candidate)
                base_urls.insert(0, candidate)
            elif candidate:
                base_urls.insert(0, f"{candidate}/ipfs")

            for candidate in base_urls:
                media_url = f"{candidate}/{content_id}"
                media_format = (
                    self.ffprobe_format(media_url)
                    if self.ffmpeg.probe_available
                    else self.http_format(media_url)
                )
                if media_format:
                    media_format["format_id"] = format_id
                    break
                media_format = {"url": media_url, "ext": "mp4", "format_id": format_id}
                self.write_debug(f"gateway {candidate!r} timed out")

            formats.append(media_format)
        self._sort_formats(formats)

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

    def avalon_api(self, endpoint, video_id):
        result = self._download_json(
            f"https://avalon.d.tube/{endpoint}",
            video_id,
            note="Downloading avalon metadata",
            errnote="Unable to download avalon metadata",
            fatal=False,
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

        exceptions = any(
            self.get_param(name)
            for name in (
                "forceurl",
                "forcejson",
                "forceformat",
                "listformats",
                "dump_single_json",
            )
        )
        if redirect_url:
            _type = "url"
            formats = None
        elif self.get_param("quiet") and self.get_param("simulate") and not exceptions:
            # we are not interested in the formats which saves us some requests
            _type = "video"
            formats = None
        elif from_playlist:
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
            "title": info.get("title"),
            "description": info.get("desc") or info.get("description"),
            "thumbnail": info.get("thumbnailUrl"),
            "tags": tags,
            "duration": info.get("duration")
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


class DTubeUserIE(DTubeIE):
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

        while True:
            result = self.avalon_api(
                f"{endpoint}/{last_id}" if last_id else endpoint, user_id
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


class DTubeQueryIE(DTubeUserIE):
    _VALID_URL = r"""(?x)
                    https?://(?:www\.)?d\.tube/
                    (?:\#!/)?
                    (?P<id>hotvideos|trendingvideos|newvideos)
                    """
    IE_NAME = "d.tube:query"

    _TESTS = [
        {
            "url": "https://d.tube/#!/hotvideos",
            "playlist_mincount": 100,
            "info_dict": {
                "id": "hotvideos",
                "title": "hotvideos",
            },
        },
        {
            "url": "https://d.tube/trendingvideos",
            "playlist_mincount": 50,
            "info_dict": {
                "id": "trendingvideos",
                "title": "trendingvideos",
            },
        },
        {
            "url": "https://d.tube/newvideos",
            "playlist_mincount": 50,
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


class DTubeSearchIE(DTubeIE):
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
        search_term = compat_urllib_parse_unquote_plus(search_term_quoted)

        if "/t/" in url:
            # tag search
            timestamp = int((datetime.now() - timedelta(days=7)).timestamp() * 1e3)
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
                    dict(payload, **{"size": page_size, "from": offset}),
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

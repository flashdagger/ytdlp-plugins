# coding: utf-8
import json
import re

from yt_dlp.extractor.common import InfoExtractor
from yt_dlp.utils import (
    parse_iso8601,
    traverse_obj,
    int_or_none,
    HEADRequest,
    parse_duration,
)

__version__ = "2021.11.28"


# pylint: disable=abstract-method
class DTubeIE(InfoExtractor):
    _VALID_URL = r"""(?x)
                    https?://(?:www\.)?d\.tube/
                    (?:\#!/)?v/
                    (?P<uploader_id>[0-9a-z.-]+)/
                    (?P<id>\w+)
                    """
    IE_NAME = "d.tube"
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
                "format": "480p",
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
                "format": "480p",
            },
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
        # youtube forward
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

    def formats(self, files):
        url_map = {
            "ipfs": ["https://player.d.tube/ipfs", "https://ipfs.d.tube/ipfs"],
            "btfs": ["https://player.d.tube/btfs"],
        }

        for provider, base_urls in url_map.items():
            if provider in files and "vid" in files[provider]:
                break
        else:
            return []

        formats = []
        res_map = {}
        # pylint: disable=W0631
        for format_id, content_id in sorted(files[provider].get("vid", {}).items()):
            for candidate in base_urls:
                head_response = self._request_webpage(
                    HEADRequest(f"{candidate}/{content_id}"),
                    None,
                    note=False,
                    errnote=f"skipping {candidate!r}",
                    fatal=False,
                )
                if head_response is False:
                    continue
                fsize = int_or_none(head_response.headers["Content-Length"])
                height = int_or_none(format_id)
                if height:
                    res_map[fsize] = height
                formats.append(
                    {
                        "format_id": f"{height}p" if height else format_id,
                        "url": f"{candidate}/{content_id}",
                        "height": height or res_map.get(fsize),
                        "filesize": fsize,
                        "ext": head_response.headers["Content-Type"].split("/")[-1],
                    }
                )
                base_urls = [candidate]
                break
            else:
                return []
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
        )
        with open("content.json", "w", encoding="utf8") as fd:
            json.dump(result, fd, indent=4)

        return result

    def entry_from_avalon_result(self, result, from_playlist=False):
        info = result["json"]
        video_provider = info.get("files", {})
        if "youtube" in video_provider:
            redirect_url = video_provider["youtube"]
        elif "dailymotion" in video_provider:
            redirect_url = (
                f"https://www.dailymotion.com/video/{video_provider['dailymotion']}"
            )
        elif "url" in info:
            redirect_url = info["url"]
        else:
            redirect_url = None
        timestamp = result.get("ts")

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

        entry_info = {
            "_type": _type,
            "url": redirect_url or f"https://d.tube/v/{result['_id']}",
            "id": result["_id"],
            "title": info.get("title"),
            "description": info.get("desc") or info.get("description"),
            "thumbnail": info.get("thumbnailUrl"),
            "tags": list(result.get("tags", {}).keys()),
            "duration": int_or_none(info.get("dur")) or parse_duration(info.get("dur")),
            "timestamp": timestamp and timestamp * 1e-3,
            "uploader_id": result.get("author"),
        }

        if formats is not None:
            entry_info["formats"] = formats

        return entry_info

    def steemit_api(self, video_id):
        """this api supports very few urls and is not used"""

        result = self._download_json(
            "https://api.steemit.com/",
            video_id,
            note="Downloading steemit metadata",
            data=json.dumps(
                {
                    "jsonrpc": "2.0",
                    "method": "call",
                    "params": ["condenser_api", "get_state", [f"/dtube/@{video_id}"]],
                }
            ).encode(),
        )
        content = traverse_obj(result, ("result", "content", video_id))
        if content is None:
            return None
        metadata = json.loads(content["json_metadata"])

        formats = []

        return {
            "id": video_id,
            "title": content.get("title"),
            "description": traverse_obj(
                metadata, "video/content/description".split("/"), default=None
            ),
            # "thumbnail": canonical_url(info.get("snaphash")),
            "tags": traverse_obj(metadata, "video/content/tags".split("/"), default=[]),
            "duration": traverse_obj(
                metadata, "video/info/duration".split("/"), default=None
            ),
            "formats": formats,
            "timestamp": parse_iso8601(content.get("created")),
            "uploader_id": content.get("author"),
        }

    def _real_extract(self, url):
        video_id = "/".join(self._match_valid_url(url).groups())
        result = self.avalon_api(f"content/{video_id}", video_id)
        return self.entry_from_avalon_result(result)


class DTubeUserIE(DTubeIE):
    _VALID_URL = r"""(?x)
                    https?://(?:www\.)?d\.tube/
                    (?:\#!/)?c/
                    (?P<id>[0-9a-z.-]+)
                    """
    IE_NAME = "d.tube:user"

    def _real_extract(self, url):
        user_id = self._match_id(url)
        video_list = []
        last_id = None

        while True:
            endpoint = f"blog/{user_id}/{last_id}" if last_id else f"blog/{user_id}"
            result = self.avalon_api(endpoint, user_id)
            if result and result[0]["_id"] == last_id:
                video_list.extend(result[1:])
            else:
                video_list.extend(result)

            if len(result) < 50:
                break

            if result:
                last_id = result[-1]["_id"]

        return self.playlist_result(
            [
                self.entry_from_avalon_result(item, from_playlist=True)
                for item in video_list
            ],
            playlist_id=user_id,
            playlist_title=user_id,
        )

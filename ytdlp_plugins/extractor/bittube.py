# coding: utf-8
import json
from contextlib import suppress

from yt_dlp.extractor.common import InfoExtractor
from yt_dlp.utils import (
    ExtractorError,
    HEADRequest,
    OnDemandPagedList,
    clean_html,
    determine_ext,
    int_or_none,
)

__version__ = "2021.11.28"


# pylint: disable=abstract-method
class BitTubeIE(InfoExtractor):
    _VALID_URL = r"""(?x)
                    https?://(?:www\.)?bittube.tv/
                    post/
                    (?P<id>[0-9a-f-]+)
                    """
    IE_NAME = "bittube"
    BASE_URL = "https://bittube.tv/"

    _TESTS = [
        {
            "url": "https://bittube.tv/post/215f2674-6250-4bda-8955-6afe2718cca3",
            "md5": "fe6036bee0c4494f39540e65f3eb3ad6",
            "info_dict": {
                "id": "215f2674-6250-4bda-8955-6afe2718cca3",
                "title": "God Doesn't Want Anyone To Perish",
                "description": "md5:962173b9525785518eeaf14adf04ec58",
                "ext": "mp4",
                "is_live": False,
                "thumbnail": "contains:newpost/115366/bittube_115366_1640398063933.jpg?token=",
                "duration": 25.38,
                "uploader": "AnotherVoiceintheDarkness",
                "channel": "Asher Brown",
                "channel_id": "AnotherVoiceintheDarkness",
                "channel_url": "https://bittube.tv/profile/AnotherVoiceintheDarkness",
                "timestamp": float,
                "upload_date": "20211225",
                "view_count": int,
                "like_count": int,
            },
            "params": {},
        },
    ]

    def __init__(self, downloader=None):
        self._magic_token = None
        super().__init__(downloader)

    def _real_initialize(self):
        if not self._get_cookies(self.BASE_URL):
            self._request_webpage(
                HEADRequest(self.BASE_URL),
                video_id=None,
                note="Setting Cookies",
            )

    def _call_api(self, endpoint, data, video_id, what=None):
        headers = {
            "Content-Type": "application/json;charset=UTF-8",
            "X-Requested-With": "XMLHttpRequest",
        }
        result = self._download_json(
            f"{self.BASE_URL}api/{endpoint}",
            video_id,
            data=json.dumps(data, separators=(",", ":")).encode(),
            headers=headers,
            note=f"Downloading {what or 'JSON metadata'}",
        )
        with suppress(KeyError, TypeError):
            if result["success"] is False:
                raise ExtractorError(f"{endpoint}: {result['mssg']}")

        return result

    @property
    def magic_token(self):
        if self._magic_token is None:
            self._magic_token = self._call_api(
                "generate-magic-token", {}, None, what="magic token"
            )
        return self._magic_token

    def media_url(self, src):
        return src and (
            f"https://webseed1.bittube.tv/mediaServer/static/posts/"
            f"{src}?token={self.magic_token}"
        )

    def formats(self, info, details=True):
        url = info.pop("url")
        ext = determine_ext(url, default_ext="unknown_video")
        format_info = {"url": url, "ext": ext.lower()}
        if ext == "m3u8":
            format_info["ext"] = "mp4"
        elif details:
            response = self._request_webpage(
                HEADRequest(url),
                info["id"],
                note="Checking media",
                errnote="Media error",
                fatal=False,
            )
            if response:
                if ext == "unknown_video":
                    format_info["ext"] = response.headers["Content-Type"].split("/")[-1]
                format_info["filesize"] = int_or_none(
                    response.headers.get("Content-Length")
                )
        info["formats"] = [format_info]

    def entry_from_result(self, result, from_playlist=False):
        url = None
        is_live = False
        timestamp = result.get("post_time")
        duration_mins = result.get("mediaDuration")

        if result["streamactive"]:
            url = self._call_api(
                "livestream/obtaintokenurl",
                {"channel": result["streamchannel"], "feed": result["streamfeed"]},
                result.get("post_id"),
                what="token url",
            ).get("url")
            is_live = bool(url)

        entry_info = {
            "id": result.get("post_id"),
            "title": result.get("title"),
            "description": clean_html(result.get("description")),
            "url": url or self.media_url(result.get("imgSrc")),
            "is_live": is_live,
            "thumbnail": self.media_url(result.get("thumbSrc")),
            "duration": duration_mins and result.get("mediaDuration") * 60,
            "uploader": result.get("username"),
            "channel": result.get("fullname"),
            "channel_id": result.get("username"),
            "channel_url": f"{self.BASE_URL}profile/{result.get('username')}",
            "timestamp": timestamp and timestamp * 1e-3,
            "view_count": result.get("views"),
            "like_count": result.get("likes_count"),
        }
        self.formats(entry_info, details=not from_playlist)
        return entry_info

    def _real_extract(self, url):
        video_id = self._match_id(url)
        result = self._call_api("get-post", {"post_id": video_id}, video_id)
        with open("content.json", "w", encoding="utf8") as fd:
            json.dump(result, fd, indent=4)
        return self.entry_from_result(result)


# pylint: disable=abstract-method
class BitTubeUserIE(BitTubeIE):
    _VALID_URL = r"""(?x)
                    https?://(?:www\.)?bittube.tv/
                    profile/
                    (?P<id>\w+)
                    """
    IE_NAME = "bittube:user"

    _TESTS = [
        {
            # all videos from channel playlist
            "url": "https://bittube.tv/profile/AnotherVoiceintheDarkness",
            "playlist_mincount": 30,
            "info_dict": {
                "id": "AnotherVoiceintheDarkness",
                "title": "Asher Brown",
                "description": "An anonymous messenger trying to show people the truth about the "
                "world they live in.",
            },
        },
    ]

    def _paged_profile_entries(self, username, user_id, page_size):
        def fetch_page(page_number):
            offset = page_number * page_size
            result = self._call_api(
                "get-user-posts",
                {"user": user_id, "limit": page_size, "offset": offset},
                username,
                what=f"entries from offset {offset:3}",
            )
            for item in result["items"]:
                yield self.entry_from_result(item, from_playlist=True)

        return OnDemandPagedList(fetch_page, page_size)

    def _real_extract(self, url):
        page_size = 30
        username = self._match_id(url)
        details = self._call_api("get-user-details", {"username": username}, username)[
            "details"
        ]

        return self.playlist_result(
            self._paged_profile_entries(username, details["id"], page_size),
            playlist_id=username,
            playlist_title=details.get("fullname"),
            playlist_description=details.get("bio"),
        )

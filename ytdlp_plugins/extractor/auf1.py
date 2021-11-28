# coding: utf-8
import json
import re

from yt_dlp.extractor.common import InfoExtractor
from yt_dlp.extractor.peertube import PeerTubeIE
from yt_dlp.utils import (
    traverse_obj,
)
from ytdlp_plugins.utils import ParsedURL

__version__ = "2021.11.24"


# pylint: disable=abstract-method
class Auf1IE(InfoExtractor):
    IE_NAME = "auf1"
    _VALID_URL = r"""(?x)
                    https?://
                        (?:www\.)?
                        (?:auf1\.tv/)
                        (?:[^/]+/)*
                        (?P<id>[^/]+)
                    """

    _TESTS = [
        {
            "url": "https://auf1.tv/nachrichten-auf1/ampelkoalition-eine-abrissbirne-fuer-deutschland/",
            "info_dict": {
                "id": "ampelkoalition-eine-abrissbirne-fuer-deutschland",
                "title": "Christopher James joins Mike Adams to discuss Common Law and corporate "
                '"personhood" global enslavement',
                "ext": "mp4",
                "description": "md5:a35cb44d7c50d673ce48e6cd661e74ac",
                "timestamp": 1635894109,
                "upload_date": "20211102",
                "duration": 2895.0,
                "channel": "Health Ranger Report",
                "channel_id": "8c536b2f-e9a1-4e4c-a422-3867d0e472e4",
                "channel_url": "https://www.brighteon.com/channels/hrreport",
                "tags": [],
                "thumbnail": "re:https?://[a-z]+.brighteon.com/thumbnail/[a-z0-9-]+",
                "view_count": int,
                "like_count": int,
            },
            "params": {"skip_download": True, "nocheckcertificate": True},
        },
        {
            # playlist
            "url": "https://www.brighteon.com/watch/21824dea-3564-40af-a972-d014b987261b",
            "info_dict": {
                "id": "21824dea-3564-40af-a972-d014b987261b",
                "title": "U.S. Senate Impeachment Trial",
            },
            "params": {"skip_download": True},
            "playlist_mincount": 10,
        },
        {
            # channel
            "url": "https://www.brighteon.com/channels/johntheo",
            "info_dict": {
                "id": "005e4477-e415-4515-b661-48e974f4a26d",
                "title": "JohnTheo-Author",
            },
            "params": {"skip_download": True, "playlistend": 3},
            "playlist_count": 3,
        },
        {
            # categories
            "url": "https://www.brighteon.com/categories/"
            "4ad59df9-25ce-424d-8ac4-4f92d58322b9/videos",
            "info_dict": {
                "id": "4ad59df9-25ce-424d-8ac4-4f92d58322b9",
                "title": "Health & Medicine",
                "description": None,
            },
            "params": {"skip_download": True, "playlistend": 3},
            "playlist_count": 3,
        },
        {
            # test embedded urls
            "url": "https://healthfreedom.news/2020-05-20-plandemic-video-super-viral-brighteon-"
            "facebook-banning-cleansing-content-wuhan-coronavirus.html",
            "info_dict": {
                "id": "2020-05-20-plandemic-video-super-viral-brighteon-facebook-banning-"
                "cleansing-content-wuhan-coronavirus",
                "title": str,
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

    def _real_extract(self, url):
        video_id = self._match_id(url)
        parsed_url = ParsedURL(url)
        webpage = self._download_webpage(url, video_id=video_id)
        match = self._html_search_regex(
            r"<link\s+[^>]*href=\"([^\"]+/payload.js)", webpage, "payload"
        )
        payload_url = f"{parsed_url.scheme}://{parsed_url.netloc}{match}"
        payload = self._download_webpage(payload_url, video_id=video_id)

        json_string = re.search(r"return\s*(.+)}", payload).group(1)
        json_string = re.sub(r"(?<=[{,])(\w+)(?=:)", r'"\1"', json_string)
        json_string = re.sub(r":[a-e](?=[,}\]])", r":null", json_string)
        json_obj = traverse_obj(json.loads(json_string), ("data", 0, "payload"))

        parsed_url = ParsedURL(json_obj["videoUrl"])
        peertube_url = f"peertube:{parsed_url.netloc}:{parsed_url.path.split('/')[-1]}"
        return self.url_result(peertube_url, ie=PeerTubeIE.ie_key())

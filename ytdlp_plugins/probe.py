import re
from typing import Dict, Any

from yt_dlp.postprocessor import FFmpegPostProcessor
from yt_dlp.utils import HEADRequest, determine_ext, int_or_none, traverse_obj


# pylint: disable=too-few-public-methods
class GLOBALS:
    FFMPEG = FFmpegPostProcessor()
    LAST_METADATA: Dict[str, Any] = {}


def codec_name(info):
    formats = {"h264": "avc1", "aac": "mp4a", "mpeg4": "mp4v"}
    profiles = {
        "Simple Profile": (0x14, 0, 3),
        "Baseline": (0x42, 0, 0),
        "Constrained Baseline": (0x42, 0x40, 0),
        "LC": (0x28, 0, 2),
        "HE-AAC": (0x28, 0, 5),
        "Main": (0x4D, 0x40, 0),
        "High": (0x64, 0, 0),
    }

    cname = info.get("codec_name", "none")
    fmt = formats.get(cname, cname)
    profile_name = info.get("profile", "???")
    match = re.match(r"Profile\s+(\d+)", profile_name)
    if match:
        profile = int(match.group(1))
        level = None
        constraint = 0
    else:
        profile, constraint, level = profiles.get(profile_name, ("???", 0, 0))

    level = info.get("level", 0) or level
    if level and level < 0:
        level = "???"

    if fmt == "avc1" and isinstance(level, int) and isinstance(profile, int):
        tag = f"{fmt}.{profile:02x}{constraint:02x}{level:02x}"
    else:
        tag = f"{fmt}.{profile}.{level}"

    return cname if "?" in tag else tag


def determine_bitrate(info):
    for path in ("tags/variant_bitrate", "bit_rate"):
        bitrate = int_or_none(
            traverse_obj(info, path.split("/"), expected_type=str), scale=1000
        )
        if bitrate:
            break
    return bitrate


def parse_streams(metadata):
    v_stream = {}
    a_stream = {}
    stream_index = []

    def fps():
        if "r_frame_rate" in v_stream:
            match = re.match(r"(\d+)(?:/(\d+))?", v_stream["r_frame_rate"])
            if match:
                nom, den = match.groups()
                return round(int(nom) / int(den or 1))
        return None

    for stream in sorted(
        metadata["streams"],
        reverse=True,
        key=lambda item: (item.get("height", 0), determine_bitrate(item) or 0),
    ):
        if not v_stream and stream["codec_type"] == "video":
            v_stream.update(stream)
            stream_index.append(stream["index"])
        elif not a_stream and stream["codec_type"] == "audio":
            a_stream.update(stream)
            stream_index.append(stream["index"])

    extension_map = {
        "matroska": "webm",
        "asf": "wmv",
        "hls": "mp4" if v_stream else "m4a",
        "dash": "mp4" if v_stream else "m4a",
        "mp4": "mp4" if v_stream else None,
        "m4a": "m4a",
        "mpegts": "ts",
        "mpeg": "mpg",
        "jpeg": "jpg",
    }
    extensions = metadata["format"]["format_name"].replace("_pipe", "").split(",")
    for ext in extensions:
        candidate = extension_map.get(ext)
        if candidate:
            extension = candidate
            break
    else:
        extension = extensions[0]

    abr = determine_bitrate(a_stream)
    vbr = determine_bitrate(v_stream)
    tbr = (
        determine_bitrate(metadata["format"])
        or (abr and vbr and abr + vbr)
        or (not v_stream and abr)
        or (not a_stream and vbr)
        or None
    )

    return {
        "ext": extension,
        "acodec": codec_name(a_stream),
        "vcodec": codec_name(v_stream),
        "asr": int_or_none(a_stream.get("sample_rate")),
        "fps": fps(),
        "tbr": tbr,
        "vbr": vbr,
        "abr": abr,
        "height": int_or_none(v_stream.get("height")),
        "width": int_or_none(v_stream.get("width")),
        "filesize": int_or_none(metadata["format"].get("size"))
        if metadata["format"].get("format_name") not in {"hls", "dash"}
        else None,
        "format": metadata["format"].get("format_long_name"),
        "duration": int(float(metadata["format"].get("duration", 0.0))) or None,
        "_stream_index": stream_index,
    }


def ffprobe_media(self, media_url, options=(), timeout_s=2.0):
    # Invoking ffprobe to determine resolution
    self.to_screen("Checking media with ffprobe")
    timeout_us = self.get_param("socket_timeout") or timeout_s
    metadata = GLOBALS.FFMPEG.get_metadata_object(
        media_url,
        opts=(
            "-show_error",
            "-show_programs",
            "-fflags",
            "+ignidx",
            "-timeout",
            str(int(timeout_us * 1e6)),
            *options,
        ),
    )
    GLOBALS.LAST_METADATA = metadata
    err_msg = traverse_obj(metadata, ("error", "string"))
    if err_msg:
        self.report_warning(f"ffprobe failed: {err_msg}")
        return []

    ffprobe_formats = []
    if len(metadata.get("programs", ())) > 1:
        for program in metadata["programs"]:
            ffprobe_formats.append(
                {
                    "url": media_url,
                    "protocol": "http_dash_segments",
                    "fragments": [],
                    "manifest_url": media_url,
                    "manifest_stream_number": f"p:{program['program_id']}",
                    **parse_streams(
                        {
                            "streams": program["streams"],
                            "format": {**metadata["format"], **program},
                        }
                    ),
                }
            )
    elif (
        len(metadata.get("programs", ())) == 1
        and metadata["format"].get("nb_streams", 0) > 2
        and metadata["format"].get("format_name") == "dash"
    ):
        for stream in metadata["programs"][0].get("streams", ()):
            ffprobe_formats.append(
                {
                    "url": media_url,
                    "protocol": "http_dash_segments",
                    "fragments": [],
                    "manifest_url": media_url,
                    "manifest_stream_number": stream["index"],
                    **parse_streams(
                        {
                            "streams": [stream],
                            "format": metadata["format"],
                        }
                    ),
                }
            )
    else:
        ffprobe_formats.append({"url": media_url, **parse_streams(metadata)})

    return ffprobe_formats


def headprobe_media(self, media_url):
    # pylint: disable=protected-access
    response = self._request_webpage(
        HEADRequest(media_url),
        video_id=None,
        note="Checking media url",
        errnote="Media error",
        fatal=False,
    )
    format_info = {
        "url": media_url,
        "ext": determine_ext(media_url, default_ext="unknown_video"),
    }
    if response:
        ctype = response.headers["Content-Type"]
        match = re.match(
            "^(?:audio|video|image)/(?:[a-z]+[-.])*([a-zA-Z1-9]{2,})(?:$|;)", ctype
        )
        if match and format_info["ext"] == "unknown_video":
            format_info["ext"] = match.group(1).lower()
        format_info["filesize"] = int_or_none(response.headers.get("Content-Length"))

    return [format_info]


def probe_media(self, media_url):
    if GLOBALS.FFMPEG.probe_available:
        probed_formats = ffprobe_media(self, media_url)
        if probed_formats:
            return probed_formats

    return headprobe_media(self, media_url)

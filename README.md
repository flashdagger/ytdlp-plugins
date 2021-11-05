# a plugin manager for yt-dlp

## about ytdlp-plugins
`ytdlp-plugins` extends the possibilities of yt-dlp by allowing to install new extractors from python packages.

For example: currently yt-dlp has very limited support for [brighteon.com](https://www.brighteon.com) videos.

But you can install the ytdlp-brighteon package (`pip install ytdlp-brighteon`) and now you have full support for livestreams, channels and playlists:

```
>>> ytdlp-plugins https://brighteon.tv -F
[brighteontv] live: Downloading webpage
[brighteontv] live: Downloading webpage
[brighteontv] brighteontv-daily-show: Downloading m3u8 information
[info] Available formats for brighteontv-daily-show:
ID       EXT RESOLUTION |   TBR PROTO  | VCODEC    VBR ACODEC   ABR
-------- --- ---------- - ----- ------ - ------- ----- ------- ----
hls-240p mp4 426x240    |  264k m3u8_n | unknown  264k unknown   0k
hls-360p mp4 640x360    |  914k m3u8_n | unknown  914k unknown   0k
hls-720p mp4 1280x720   | 2628k m3u8_n | unknown 2628k unknown   0k
```

these plugin packages are currently available:
* [ytdlp-brighteon](https://pypi.org/project/ytdlp-brighteon/)
* [ytdlp-youmaker](https://pypi.org/project/ytdlp-youmaker/)
* [ytdlp-servustv](https://pypi.org/project/ytdlp-servustv/)


## about yt-dlp
yt-dlp is a [youtube-dl](https://github.com/ytdl-org/youtube-dl) fork based on the now inactive [youtube-dlc](https://github.com/blackjack4494/yt-dlc). The main focus of this project is adding new features and patches while also keeping up to date with the original project

Note that **all** plugins are imported even if not invoked, and that **there are no checks** performed on plugin code. Use plugins at your own risk and only if you trust the code


## installation
You can install ytdlp-lugins via pip:
* Use [PyPI package](https://pypi.org/project/yt-dlp): 

  `python3 -m pip install --upgrade ytdlp-plugins`
* Install from Github branch: 

  `python3 -m pip3 install -U https://github.com/flashdagger/ytdlp-plugins/archive/refs/heads/master.zip`

Note that on some systems, you may need to use `py` or `python` instead of `python3`

## running example
ytdlp-plugins enables all plugins and forwards all parameters to yt-dlp:

`ytdlp-plugins --list-extractors`

or

`python3 -m ytdlp-plugins --list-extractors`


## running tests
You can run the extractor unittests on all installed plugins:

`python3 -m unittest ytdlp_plugins.test_download`

or with pytest

`pytest --pyargs ytdlp_plugins.test_download`

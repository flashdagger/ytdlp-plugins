# bittube.tv support for yt-dlp
* record live streaming
* support embedded YouTube videos
* support for user profile playlists (e.g. https://bittube.tv/profile/bittube)
* query urls with media-type and term filter (e.g. https://bittube.tv/explore/explore-videos?term=crypto&navigation=Trending)
* topic hashtag playlists (e.g. https://bittube.tv/topic/bittube)

## installation

You can install ytdlp-bittube via pip:

* Use [PyPI package](https://pypi.org/project/yt-dlp):

  `python3 -m pip install --upgrade ytdlp-bittube`
* Install from Github branch:

  `python3 -m pip install -U https://github.com/flashdagger/ytdlp-plugins/archive/refs/heads/bittube.zip`

Note that on some systems, you may need to use `py` or `python` instead of `python3`

## example: show the 20 recent titles from user channel

`python3 -m ytdlp_plugins -e --playlist-items 1-20 https://bittube.tv/profile/UrsachenforschungGtz`

## yt-dlp

[yt-dlp](https://github.com/yt-dlp/yt-dlp) is a [youtube-dl](https://github.com/ytdl-org/youtube-dl) fork based on the now
inactive [youtube-dlc](https://github.com/blackjack4494/yt-dlc). The main focus of this project is adding new features
and patches while also keeping up to date with the original project

Note that **all** plugins are imported even if not invoked, and that **there are no checks** performed on plugin code.
Use plugins at your own risk and only if you trust the code


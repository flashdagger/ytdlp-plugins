> **_NOTE_:**  
> 
> Since version 2023.01.06 yt-dlp supports plugins from python packages.
> The ytdlp-plugins package is no longer necessary.
> 
> For further details see https://github.com/yt-dlp/yt-dlp#plugins

# youmaker.com support for yt-dlp

## installation

You can install ytdlp-youmaker via pip:

* Use [PyPI package](https://pypi.org/project/yt-dlp):

  `python3 -m pip install --upgrade ytdlp-youmaker`
* Install from GitHub branch:

  `python3 -m pip install -U https://github.com/flashdagger/ytdlp-plugins/archive/refs/heads/youmaker.zip`

Note that on some systems, you may need to use `py` or `python` instead of `python3`

## example: show the 20 recent titles from channel

`python3 -m yt_dlp -e --playlist-items :20 --flat-playlist https://youmaker.com/channel/ntd`


## about yt-dlp

[yt-dlp](https://github.com/yt-dlp/yt-dlp) is a [youtube-dl](https://github.com/ytdl-org/youtube-dl) fork based on the now
inactive [youtube-dlc](https://github.com/blackjack4494/yt-dlc). The main focus of this project is adding new features
and patches while also keeping up to date with the original project

Note that **all** plugins are imported even if not invoked, and that **there are no checks** performed on plugin code.
Use plugins at your own risk and only if you trust the code


> **_NOTE_:**  
> 
> Since version 2023.01.06 yt-dlp supports plugins from python packages.
> Yet the ytdlp-plugins package remains as a direct dependency.
> 
> For further details see https://github.com/yt-dlp/yt-dlp#plugins

# d.tube support for yt-dlp

* support for user channel playlists (e.g. https://d.tube/#!/c/dtube)
* query urls (e.g. https://d.tube/#!/newvideos)
* searches (e.g. https://d.tube/#!/s/crypto)

## installation

You can install ytdlp-dtube via pip:

* Use [PyPI package](https://pypi.org/project/yt-dlp):

  `python3 -m pip install --upgrade ytdlp-dtube`
* Install from GitHub branch:

  `python3 -m pip install -U https://github.com/flashdagger/ytdlp-plugins/archive/refs/heads/dtube.zip`

Note that on some systems, you may need to use `py` or `python` instead of `python3`

## example: show the titles of the 20 most recent trending videos

`python3 -m yt_dlp -e --flat-playlist --playlist-items :20 https://d.tube/trendingvideos`

## yt-dlp

[yt-dlp](https://github.com/yt-dlp/yt-dlp) is a [youtube-dl](https://github.com/ytdl-org/youtube-dl) fork based on the now
inactive [youtube-dlc](https://github.com/blackjack4494/yt-dlc). The main focus of this project is adding new features
and patches while also keeping up to date with the original project

Note that **all** plugins are imported even if not invoked, and that **there are no checks** performed on plugin code.
Use plugins at your own risk and only if you trust the code


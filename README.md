# servustv.com support for yt-dlp

* supported domains: [servustv.com](https://servustv.com) and [pm-wissen.com](https://pm-wissen.com)
* supported live channels:
  * [Hauptkanal](https://www.servustv.com/allgemein/p/jetzt-live/119753/) 
  * [Wetterpanorama](https://www.servustv.com/aktuelles/v/aa9bgcvsvf7sq8y4sm14/) 
  * [Kanal: Natur](https://www.servustv.com/natur/k/natur-kanal/269299/)
  * [Kanal: Wissen](https://www.servustv.com/wissen/k/wissen-kanal/269302/)
* playlist from topics (e.g. [Servus Nachrichten](https://www.servustv.com/aktuelles/b/servus-nachrichten/aa-1y5rjcd1h2111/)
  or [Motorsport](https://www.servustv.com/sport/p/motorsport/325/))
* playlist from searches (e.g. [search term 'Spielfilme'](https://www.servustv.com/search/spielfilme/))

## installation

You can install ytdlp-servustv via pip:

* Use [PyPI package](https://pypi.org/project/yt-dlp):

  `python3 -m pip install --upgrade ytdlp-servustv`
* Install from GitHub branch:

  `python3 -m pip install -U https://github.com/flashdagger/ytdlp-plugins/archive/refs/heads/servustv.zip`

Note that on some systems, you may need to use `py` or `python` instead of `python3`

## example: show all titles from channel

  `python3 -m ytdlp_plugins -e https://www.servustv.com/unterhaltung/b/spielfilme/aa-1u4ebfxk52111/`


## yt-dlp

[yt-dlp](https://github.com/yt-dlp/yt-dlp) is a [youtube-dl](https://github.com/ytdl-org/youtube-dl) fork based on the now
inactive [youtube-dlc](https://github.com/blackjack4494/yt-dlc). The main focus of this project is adding new features
and patches while also keeping up to date with the original project

Note that **all** plugins are imported even if not invoked, and that **there are no checks** performed on plugin code.
Use plugins at your own risk and only if you trust the code


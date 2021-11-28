# a plugin manager for yt-dlp

## about ytdlp-plugins
`ytdlp-plugins` extends the possibilities of yt-dlp by allowing to install new extractors from python packages that are not part of yt-dlp.

The following plugin packages are currently available:
* [ytdlp-brighteon](https://pypi.org/project/ytdlp-brighteon/)
* [ytdlp-youmaker](https://pypi.org/project/ytdlp-youmaker/)
* [ytdlp-servustv](https://pypi.org/project/ytdlp-servustv/)


## installation
You can install ytdlp-lugins via pip:
* Use [PyPI package](https://pypi.org/project/ytdlp-plugins): 

  `python3 -m pip install --upgrade ytdlp-plugins`
* Install from Github branch: 

  `python3 -m pip install -U https://github.com/flashdagger/ytdlp-plugins/archive/refs/heads/master.zip`

Note that on some systems, you may need to use `py` or `python` instead of `python3`

## running example
ytdlp-plugins enables all plugins and forwards all parameters to yt-dlp.

You will get a detailed overview by running in verbose mode:

`ytdlp-plugins -v`


## running tests
You can run the extractor unittests on all installed plugins:

`python3 -m unittest ytdlp_plugins.test_download`

or with pytest

`pytest --pyargs ytdlp_plugins.test_download`


## about yt-dlp
yt-dlp is a [youtube-dl](https://github.com/ytdl-org/youtube-dl) fork based on the now inactive [youtube-dlc](https://github.com/blackjack4494/yt-dlc). The main focus of this project is adding new features and patches while also keeping up to date with the original project

Note that **all** plugins are imported even if not invoked, and that **there are no checks** performed on plugin code. Use plugins at your own risk and only if you trust the code

# a plugin manager for yt-dlp

## about ytdlp-plugins
`ytdlp-plugins` extends the possibilities of yt-dlp by allowing to install new extractors from python packages that are not part of yt-dlp.

The following plugin packages are currently available:
* [ytdlp-auf1](https://pypi.org/project/ytdlp-auf1/)
* [ytdlp-bittube](https://pypi.org/project/ytdlp-bittube/) *(service is inoperative)*
* [ytdlp-brighteon](https://pypi.org/project/ytdlp-brighteon/)
* [ytdlp-dtube](https://pypi.org/project/ytdlp-dtube/)
* [ytdlp-servustv](https://pypi.org/project/ytdlp-servustv/)
* [ytdlp-youmaker](https://pypi.org/project/ytdlp-youmaker/)


## installation
You can install ytdlp-plugins via pip:
* Use [PyPI package](https://pypi.org/project/ytdlp-plugins): 

  `python3 -m pip install --upgrade ytdlp-plugins`
* Install from GitHub branch: 

  `python3 -m pip install -U https://github.com/flashdagger/ytdlp-plugins/archive/refs/heads/master.zip`

Note that on some systems, you may need to use `py` or `python` instead of `python3`

## running from command-line
On the command-line line simply use `ytdlp-plugins` executable instead `yt-dlp`.
This enables all plugins and forwards all parameters to yt-dlp.

You will get a detailed overview of installed plugins by running in verbose mode:

`ytdlp-plugins -v`


## embedding in your code

```python
import ytdlp_plugins
from yt_dlp import YoutubeDL

# add found plugin extractors to yt-dlp
ytdlp_plugins.add_plugins()

URLS = ['https://www.servustv.com/allgemein/p/jetzt-live/119753/']
with YoutubeDL() as ydl:
  ydl.download(URLS)
```

For more details see [embedding yt-dlp](https://github.com/yt-dlp/yt-dlp#embedding-yt-dlp)


## running tests
You can run the extractor unittests on all installed plugins:

`python3 -m unittest ytdlp_plugins.test_download`

or with pytest

`pytest --pyargs ytdlp_plugins.test_download`


## creating packages
Want to create your own extractor package or simply apply 
a patch to an existing (internal) yt-dlp extractor? Awesome.
Just check out the [minimal branch](https://github.com/flashdagger/ytdlp-plugins/tree/minimal)
and follow the instructions in the provided README.md:

`git clone https://github.com/flashdagger/ytdlp-plugins.git --branch minimal`


## about yt-dlp
[yt-dlp](https://github.com/yt-dlp/yt-dlp) is a [youtube-dl](https://github.com/ytdl-org/youtube-dl) fork based on the now inactive [youtube-dlc](https://github.com/blackjack4494/yt-dlc). The main focus of this project is adding new features and patches while also keeping up to date with the original project

Note that **all** plugins are imported even if not invoked, and that **there are no checks** performed on plugin code. Use plugins at your own risk and only if you trust the code

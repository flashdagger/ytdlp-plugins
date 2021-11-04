# example package for a yt-dlp plugin

## INSTALLATION
You can install ytdlp-testpluginB via pip:
* Use [PyPI package](https://pypi.org/project/yt-dlp): 

  `python3 -m pip install --upgrade ytdlp-testpluginB`
* Install from Github branch: 

  `python3 -m pip3 install -U https://github.com/flashdagger/ytdlp-plugins/archive/refs/heads/testpluginB.zip`

Note that on some systems, you may need to use `py` or `python` instead of `python3`

## running example
`python3 -m yt-dlp -s testpluginB:badeaffe`

The output should be:
```
[TestPluginA] URL "testpluginB:badeaffe" sucessfully captured
[info] badeaffe: Downloading 1 format(s): 0
```


## yt-dlp
yt-dlp is a [youtube-dl](https://github.com/ytdl-org/youtube-dl) fork based on the now inactive [youtube-dlc](https://github.com/blackjack4494/yt-dlc). The main focus of this project is adding new features and patches while also keeping up to date with the original project

Plugins are loaded from `<root-dir>/ytdlp_plugins/<type>/__init__.py`; where `<root-dir>` is the directory of the binary (`<root-dir>/yt-dlp`), or the root directory of the module if you are running directly from source-code (`<root dir>/yt_dlp/__main__.py`). Plugins are currently not supported for the `pip` version

Plugins can be of `<type>`s `extractor` or `postprocessor`. Extractor plugins do not need to be enabled from the CLI and are automatically invoked when the input URL is suitable for it. Postprocessor plugins can be invoked using `--use-postprocessor NAME`.

Note that **all** plugins are imported even if not invoked, and that **there are no checks** performed on plugin code. Use plugins at your own risk and only if you trust the code


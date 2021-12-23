# create your own yt-dlp extractor

## install the project as editable package
`pip install -e .`

## implement the extractor
Simply put the code under `ytdlp_plugins/extractor/<name>.py`.

Test by executing the extractor:

`ytdlp-plugins -v <url>`

## create the package
Edit `setup.cfg` according to your needs. 
For details see https://setuptools.pypa.io/en/latest/userguide/declarative_config.html

Create a wheel package:

```
python -m pip install -U setuptools wheel
python setup.py bdist_wheel
```

Celebrate 🥳 !!!
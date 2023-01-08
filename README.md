# create your own yt-dlp extractor

## install the project as editable package
`pip install -e .`

## implement the extractor
Simply put the code under `yt_dlp_plugins/extractor/<name>.py`.

Test by executing the extractor:

`yt-dlp -v <url>`

or just run the unit tests:

`python .\setup.py test`

## create the package
Edit `setup.cfg` according to your needs. 
For details see https://setuptools.pypa.io/en/latest/userguide/declarative_config.html

Create a wheel package:

```
python -m pip install -U setuptools wheel
python setup.py bdist_wheel
```

If the build is succesful your package can be found in `build/<name>-<version>-py3-none-any.whl`.
You can then install it with `pip` or upload to [PyPI](https://pypi.org).

For more information about packaging see https://packaging.python.org/en/latest/tutorials/packaging-projects/.

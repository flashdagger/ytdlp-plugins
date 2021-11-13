#!/usr/bin/env python
# -*- coding: UTF-8 -*-

from yt_dlp import main as ytdlp_main

from . import initialize, add_plugins
from .patching import patch_decorator


@patch_decorator
def main(argv=None):
    initialize()
    add_plugins()
    ytdlp_main(argv=argv)


if __name__ == "__main__":
    main()

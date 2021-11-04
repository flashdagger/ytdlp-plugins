# coding: utf-8

import sys
from pathlib import Path

if __package__ is None and getattr(sys, "frozen", False) is False:
    root_path = Path(__file__).parents[1]
    sys.path.insert(0, str(root_path))

if __name__ == "__main__":
    import ytdlp_plugins

    ytdlp_plugins.main()

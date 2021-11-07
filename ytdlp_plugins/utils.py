#!/usr/bin/env python
# -*- coding: UTF-8 -*-


def estimate_filesize(formats, duration):
    if not (formats and duration):
        return

    for item in formats:
        if any(map(item.get, ("filesize", "filesize_approx", "fs_approx"))):
            continue
        tbr = item.get("tbr")
        if tbr:
            item["filesize_approx"] = 128 * tbr * duration

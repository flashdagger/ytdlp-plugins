#!/usr/bin/env python
# -*- coding: UTF-8 -*-


def estimate_filesize(formats, duration):
    if not duration:
        return
    for item in formats:
        if item.get("filesize") or item.get("filesize_approx"):
            continue
        tbr = item.get("tbr")
        if tbr:
            item["filesize_approx"] = 128 * tbr * duration

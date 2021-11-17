#!/usr/bin/env python
# -*- coding: UTF-8 -*-
from contextlib import suppress
from importlib import import_module
from inspect import getfullargspec
from typing import List, Optional, Callable, Dict, Any

from yt_dlp.extractor.common import InfoExtractor
from yt_dlp.extractor.generic import GenericIE as GenericExtractor
from yt_dlp.utils import HEADRequest, sanitized_Request, is_html, orderedSet


def unlazify(cls) -> InfoExtractor:
    """if extractor class is lazy type, return the actual class"""
    with suppress(AttributeError, ImportError):
        actual_module = getattr(cls, "_module")
        module = import_module(actual_module)
        cls = getattr(module, cls.__name__)
    return cls


# pylint: disable=abstract-method
class GenericIE(GenericExtractor):
    REQUEST_CACHE: Dict[str, Any] = {}
    OTHER_EXTRACTORS: List[InfoExtractor] = []

    def call_url_extract(self, cls: InfoExtractor, webpage: str, url: str) -> List[str]:
        func: Optional[Callable] = getattr(cls, "_extract_urls", None)
        if func is None:
            func = getattr(cls, "_extract_url", None)
        if func is None:
            return []
        args = getfullargspec(func).args
        if args[0] == "cls":
            args = args[1:]
        if args[0] != "webpage":
            return []
        call_args = [webpage]
        if len(args) == 2 and "url" in args[1]:
            call_args.append(url)

        try:
            urls = func(*call_args)
        except Exception:  # pylint: disable=broad-except
            self.report_warning(f"Error while calling {cls.__name__}.{func.__name__}()")
            urls = []

        if isinstance(urls, str):
            urls = [urls]

        if self.get_param("verbose", False) and urls:
            self.to_screen(
                f"{cls.__name__}.{func.__name__}() returned {len(urls)} url(s)"
            )

        return urls

    def _og_search_title(self, html, **kwargs):
        site_name = self._og_search_property("site_name", html, default=None)
        title = super()._og_search_title(html, **kwargs)
        if site_name and title:
            title = title.replace(f" - {site_name}", "", 1)

        return title

    def _request_webpage(self, url_or_request, *args, **kwargs):
        if url_or_request not in self.REQUEST_CACHE:
            self.REQUEST_CACHE[url_or_request] = super()._request_webpage(
                url_or_request, *args, **kwargs
            )

        return self.REQUEST_CACHE[url_or_request]

    def _real_extract(self, url):
        video_id = self._generic_id(url)
        head_req = HEADRequest(url)
        head_response = self._request_webpage(
            head_req,
            video_id,
            note=False,
            errnote=f"Could not send HEAD request to {url}",
            fatal=False,
        )

        with suppress(AssertionError):
            assert head_response
            content_type = head_response.headers.get("Content-Type", "").lower()
            assert content_type.startswith("text/html")

            # Check for redirect
            new_url = head_response.geturl()
            if url != new_url:
                self.report_following_redirect(new_url)
                return self.url_result(new_url)

            request = sanitized_Request(url)
            request.add_header("Accept-Encoding", "*")
            full_response = self._request_webpage(request, video_id)
            assert full_response
            first_bytes = full_response.read(512)
            assert is_html(first_bytes)

            webpage = self._webpage_read_content(
                full_response, url, video_id, prefix=first_bytes
            )
            for extractor in self.OTHER_EXTRACTORS:
                extractor = unlazify(extractor)
                urls = orderedSet(self.call_url_extract(extractor, webpage, url))
                if urls:
                    return self.playlist_from_matches(
                        urls,
                        video_id,
                        playlist_title=self._og_search_title(
                            webpage, default=self._generic_title(url)
                        ),
                        ie=extractor.ie_key(),
                    )

        return super()._real_extract(url)

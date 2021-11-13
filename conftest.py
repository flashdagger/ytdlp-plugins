#!/usr/bin/env python
# -*- coding: UTF-8 -*-


def pytest_addoption(parser):
    parser.addoption("--all", action="store_true", default=False)

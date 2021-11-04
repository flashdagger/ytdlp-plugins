#!/usr/bin/env python

from __future__ import print_function
import os
import sys

if __name__ == "__main__":
    cwd, _ = os.path.split(sys.argv[0])
    if os.name == "nt":
        python_exe = os.path.join(cwd, "venv", "Scripts", "python.exe")
    else:
        assert os.name == "posix"
        python_exe = os.path.join(cwd, "venv", "bin", "python")

    if not os.path.exists(python_exe):
        print("ERROR: Could not find %s" % python_exe, file=sys.stderr)
        sys.exit(1)
    cmd = python_exe + " -m " + " ".join(sys.argv[1:])
    ret = os.system(cmd)
    sys.exit(ret)

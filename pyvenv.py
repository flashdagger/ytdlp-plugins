#!/usr/bin/env python
# -*- coding: utf-8 -*-


"""
main entry point for the module
"""
import argparse
import hashlib
import importlib.util
import logging
import os
import re
import shutil
import sys
from contextlib import contextmanager
from pathlib import Path
from subprocess import check_call, CalledProcessError, call, check_output
from typing import Any

HASH_ALGO = "md5"
CURRENT_PATH = Path(__file__).parent.absolute()
REQ_TXT = (CURRENT_PATH / "requirements.txt").relative_to(Path.cwd())
REQ_IN = CURRENT_PATH / "requirements.in"
WINDOWS = sys.platform.startswith("win")
LINUX = sys.platform.startswith("linux")

LOG = logging.getLogger("PYVENV")


# pylint: disable=too-few-public-methods
class GLOBALS:
    min_version = "3.6"


def save_relative_to(from_path, to_path=None):
    if to_path is None:
        to_path = Path.cwd()

    try:
        return from_path.relative_to(to_path)
    except ValueError:
        return Path(os.path.relpath(from_path, to_path))


def setup_logging(default_level="WARNING"):
    logging.basicConfig(format="%(name)s:%(levelname)s: %(message)s")
    LOG.setLevel(logging.getLevelName(default_level))


def assert_module(name) -> Any:
    spec = importlib.util.find_spec(name)  # type: ignore
    module = spec and spec.loader and importlib.import_module(name)
    if module:
        return module
    LOG.error("Cannot load module %s.", name)
    sys.exit(1)


def assert_python_version():
    min_tuple = tuple(int(digit) for digit in GLOBALS.min_version.split("."))
    this_version = ".".join(map(str, sys.version_info[:3]))

    if min_tuple < (3, 5):
        LOG.warning("Python version <3.5 is not recommended.")

    if sys.version_info >= min_tuple:
        return

    LOG.error(
        "%s is version %s. We need at least %s.",
        sys.executable,
        this_version,
        GLOBALS.min_version,
    )

    sys.exit(1)


def find_executable(name, path):
    if WINDOWS:
        bin_dir = path / "Scripts"
    elif LINUX:
        bin_dir = path / "bin"
    else:
        return None

    exe = shutil.which(name, path=str(bin_dir))
    return exe and Path(exe)


def patch_activate(path):
    script = find_executable("activate.bat", path)
    if not script:
        return

    content = script.read_text()
    if "delims=:." not in content:
        script.write_text(content.replace("delims=:", "delims=:."))
        LOG.info("Patched %s", script)


def assert_precommit():
    pc_path = CURRENT_PATH / ".git/hooks/pre-commit"
    if not pc_path.exists():
        pass


def check_config(path):
    config = path / "pyvenv.cfg"
    if config.exists():
        mapping = {}
        for line in config.read_text().splitlines():
            if "=" not in line:
                continue
            key, value = line.split("=", maxsplit=1)
            mapping[key.strip()] = value.strip()
        home = mapping.get("home")
        if home and Path(home).exists():
            return True
    return False


def install_venv(path: Path):
    venv = assert_module("venv")
    LOG.info("Installing virtual environment in %s", save_relative_to(path))
    venv.main([str(path)])
    patch_activate(path)


def venv_python(path):
    if not (find_executable("python", path) and check_config(path)):
        assert_python_version()
        install_venv(path)

    return find_executable("python", path)


def safe_call(cmd, **kwargs):
    try:
        check_call(cmd, **kwargs)
    except CalledProcessError as exc:
        LOG.error(exc)
        sys.exit(exc.returncode)


@contextmanager
def content_check(file: Path, path=None):
    if file.exists():
        if path is None:
            path = file.parent
        actual_hash = hashlib.new(HASH_ALGO, file.read_bytes()).hexdigest()
        hash_file = path / ".".join((file.name, sys.platform, HASH_ALGO.lower()))
        if hash_file.exists():
            saved_hash = hash_file.read_text()
        else:
            saved_hash = None

        yield saved_hash != actual_hash
        hash_file.write_text(actual_hash)
    else:
        yield False


def package_executable(venv_path: Path, package_name, executable_name):
    python_executable = venv_python(venv_path)

    if not find_executable(executable_name, venv_path):
        LOG.info("installing %s...", package_name)
        options = []

        for req_file in (REQ_IN, REQ_TXT):
            if not req_file.exists():
                continue
            for option in re.findall(r"^--.*", REQ_IN.read_text(), flags=re.MULTILINE):
                options.extend(option.split())
            break

        safe_call(
            [str(python_executable), "-m", "pip", "install", *options, package_name]
        )

    return find_executable(executable_name, venv_path)


def sync(venv_path: Path):
    python_executable = venv_python(venv_path)
    assert python_executable, "{} not found".format(python_executable)

    version_b = check_output([str(python_executable), "--version"])
    LOG.info(version_b.decode().strip())

    pip_compile = package_executable(venv_path, "pip-tools", "pip-compile")
    pip_sync = package_executable(venv_path, "pip-tools", "pip-sync")
    package_executable(venv_path, "wheel", "wheel")

    with content_check(REQ_IN, path=venv_path) as has_changed:
        if not REQ_TXT.exists():
            LOG.info("Creating %s (this might take a while)", REQ_TXT.name)
            safe_call(
                [str(pip_compile), "--output-file", str(REQ_TXT), "--quiet"],
                cwd=CURRENT_PATH,
            )
        elif has_changed:
            LOG.info(
                f"%s was modified. You can run 'pip-compile --output-file={REQ_TXT}' to update.",
                REQ_IN.name,
            )

    with content_check(REQ_TXT, path=venv_path) as has_changed:
        if has_changed:
            safe_call([str(pip_sync), str(REQ_TXT)], cwd=CURRENT_PATH)
            LOG.info("Packages are up to date.")

    if (
        Path(CURRENT_PATH, ".pre-commit-config.yaml").exists()
        and find_executable("pre-commit", venv_path)
        and Path(CURRENT_PATH, ".git").exists()
        and not Path(CURRENT_PATH, ".git/hooks/pre-commit").exists()
    ):
        safe_call(
            [str(python_executable), "-m", "pre_commit", "install"], cwd=CURRENT_PATH
        )

    LOG.info("%s is up to date.", save_relative_to(venv_path))


def execute(venv_path, args) -> int:
    python_executable = venv_python(venv_path)
    if not python_executable.exists():
        LOG.error("%s does not exist.", python_executable)

    return call([str(python_executable), "-m", *args])


def activate(args):
    if args.path is None:
        for candidate in CURRENT_PATH.glob(
            "venv*/" + ("Scripts/python.exe" if WINDOWS else "bin/python")
        ):
            venv_path = candidate.parents[1]
            break
        else:
            venv_path = CURRENT_PATH / "venv"
            if venv_path.exists():
                venv_path = CURRENT_PATH / ("venv" + "_win" if WINDOWS else "_linux")
    else:
        venv_path = Path(args.path)

    if not venv_path.is_absolute():
        venv_path = CURRENT_PATH / args.path

    if hasattr(args, "run"):
        return execute(venv_path, args.run)

    sync(venv_path)

    return 0


def create_parser():
    description = "Setup and use a python virtual environment"
    parser = argparse.ArgumentParser(
        description=description,
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "--min-version",
        metavar="<version>",
        help="minimal supported Python version",
        default=".".join(map(str, sys.version_info[:2])),
    )
    parser.add_argument(
        "--path", metavar="<path>", help="directory of the virtual env", default=None
    )
    parser.add_argument(
        "-r",
        metavar="<requirements file>",
        help="use given requirements file",
        default=REQ_TXT.name,
    )
    parser.add_argument(
        "--run",
        nargs=argparse.REMAINDER,
        help="execute command in virtual environmant",
        default=argparse.SUPPRESS,
    )

    return parser


def parse_args(args):
    """parse_args(args)
    parsing commandline parameters

    :param args: arguments passed to the main function
    :type args: `List[str]`
    :rtype: :class:`Namespace`
    """

    parser = create_parser()
    return parser.parse_args(args)


def main() -> int:
    """main entry point for console script"""
    global REQ_TXT

    args = parse_args(sys.argv[1:])
    GLOBALS.min_version = args.min_version
    setup_logging("INFO")
    REQ_TXT = REQ_TXT.with_name(args.r)
    return activate(args)


if __name__ == "__main__":
    sys.exit(main())

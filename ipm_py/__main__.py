
from .install import do_install
from .download import do_download
from .build import do_build
import argparse
import os
import sys
import logging
logging.basicConfig(level=logging.INFO)

"""
ipm install -S <url> downloads url and installs the package systemwide, potentially compiling it
ipm install -U <url> same as above, but userwide
ipm install <url> <path> same as above, but to the specified path
ipm download <url> [path] downloads the package to path, or the current working directory if not specified
ipm build [path] builds the project at path or the current working directory if not specified
"""


if __name__ == "__main__":
    parser = argparse.ArgumentParser(prog="ipm-py")
    subparsers = parser.add_subparsers(title="Actions", required=True)

    install_command = subparsers.add_parser("install")
    group = install_command.add_mutually_exclusive_group()
    group.add_argument(
        "-S", "--system", action="store_true", help="Install package system-wide")
    group.add_argument(
        "-U", "--user", action="store_false", help="Install package user-wide")
    install_command.add_argument(
        "url", help="Location of the package")
    group.add_argument(
        "path", help="Install package to the given path", nargs='?')
    install_command.set_defaults(action=do_install)

    download_command = subparsers.add_parser("download")
    download_command.add_argument(
        "url", help="Location of the package")
    download_command.add_argument(
        "path", help="Download package to the given path", nargs='?', default=os.getcwd())
    download_command.set_defaults(action=do_download)

    build_command = subparsers.add_parser("build")
    build_command.add_argument(
        "path", help="Build package in the given path", nargs='?', default=os.getcwd())
    build_command.set_defaults(action=do_build)

    if len(sys.argv) == 1:
        parser.parse_args(["--help"])
        exit(1)

    result = parser.parse_args()
    result.action(result)

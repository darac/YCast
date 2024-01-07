#!/usr/bin/env python3
from __future__ import annotations

import argparse
import logging
import platform
import signal
import sys
from pathlib import Path
from typing import TYPE_CHECKING

from ycast import __version__, server

if TYPE_CHECKING:
    from types import FrameType

logging.basicConfig(
    format="%(asctime)s %(levelname)-8s [%(name)s]: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    level=logging.INFO,
)
LOG = logging.getLogger(__name__)


def handler(signum: int, _frame: FrameType | None) -> None:
    LOG.info("Signal %s received: rereading filter config", signal.getsignal(signum))
    from ycast.my_filter import init_filter_file

    init_filter_file()


signal.signal(signal.SIGHUP, handler)


def launch_server() -> None:
    parser = argparse.ArgumentParser(description="vTuner API emulation")
    parser.add_argument(
        "-c",
        action="store",
        dest="config",
        help="Station configuration",
        default=None,
        type=lambda p: Path(p).absolute(),
    )
    parser.add_argument(
        "-l", action="store", dest="address", help="Listen address", default="127.0.0.1"
    )
    parser.add_argument(
        "-p", action="store", dest="port", type=int, help="Listen port", default=80
    )
    parser.add_argument("-d", action="store_true", dest="debug", help="Enable debug logging")
    arguments = parser.parse_args()
    LOG.info("YCast (%s) server starting", __version__)
    if arguments.debug:
        logging.getLogger().setLevel(logging.DEBUG)
        LOG.debug("Debug logging enabled")
    else:
        logging.getLogger("werkzeug").setLevel(logging.WARNING)

    # initialize important ycast parameters
    from ycast.generic import init_base_dir

    init_base_dir("ycast")
    from ycast.my_filter import init_filter_file

    init_filter_file()

    server.run(arguments.config, arguments.address, arguments.port)


if __name__ == "__main__":
    if sys.version_info < (3, 10):
        LOG.error(
            "Unsupported Python version (Python %s). Minimum required version is Python 3.10.",
            platform.python_version,
        )
        sys.exit(1)
    launch_server()

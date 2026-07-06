"""Logging setup for ytcap."""

from __future__ import annotations

import logging


LOGGER_NAME = "ytcap"


def configure_logging(*, verbose: bool = False, quiet: bool = False) -> None:
    level = logging.INFO
    if verbose:
        level = logging.DEBUG
    if quiet:
        level = logging.ERROR

    logging.basicConfig(level=level, format="%(levelname)s: %(message)s")
    logging.getLogger(LOGGER_NAME).setLevel(level)

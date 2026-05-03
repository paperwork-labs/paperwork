"""Reset logging state between middleware tests."""

from __future__ import annotations

import logging
from collections.abc import Iterator

import pytest

from api_foundation.middleware import ACCESS_LOGGER_NAME


@pytest.fixture(autouse=True)
def _isolate_access_logger() -> Iterator[None]:
    lg = logging.getLogger(ACCESS_LOGGER_NAME)
    lg.handlers.clear()
    lg.setLevel(logging.DEBUG)
    lg.propagate = False
    yield
    lg.handlers.clear()

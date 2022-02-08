import logging

from .client import AsyncFirebaseClient  # noqa

root_logger = logging.getLogger("async_firebase")
if root_logger.level == logging.NOTSET:
    root_logger.setLevel(logging.WARN)

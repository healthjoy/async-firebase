import logging

from .client import AsyncFirebaseClient  # noqa
from .messages import (  # noqa
    AndroidConfig,
    APNSConfig,
    FCMBatchResponse,
    FCMResponse,
    Message,
    MulticastMessage,
    TopicManagementResponse,
    WebpushConfig,
)


__all__ = [
    "AsyncFirebaseClient",
    "AndroidConfig",
    "APNSConfig",
    "FCMBatchResponse",
    "FCMResponse",
    "Message",
    "MulticastMessage",
    "TopicManagementResponse",
    "WebpushConfig",
]

root_logger = logging.getLogger("async_firebase")
if root_logger.level == logging.NOTSET:
    root_logger.setLevel(logging.WARN)

import typing as t
from dataclasses import dataclass


@dataclass()
class RequestTimeout:
    """
    Request timeout configuration.

    Arguments:
    timeout: Timeout on all operations eg, read, write, connect.

    Examples:
        RequestTimeout(None)               # No timeouts.
        RequestTimeout(5.0)                # 5s timeout on all operations.
    """

    timeout: t.Optional[float] = None


@dataclass()
class RequestLimits:
    """
    Configuration for request limits.

    Attributes:
    max_connections: The maximum number of concurrent connections that may be established.
    max_keepalive_connections: Allow the connection pool to maintain keep-alive connections
        below this point. Should be less than or equal to `max_connections`.
    keepalive_expiry: Time limit on idle keep-alive connections in seconds.
    """

    max_connections: t.Optional[int] = None
    max_keepalive_connections: t.Optional[int] = None
    keepalive_expiry: t.Optional[int] = None


DEFAULT_REQUEST_TIMEOUT = RequestTimeout(timeout=5.0)
DEFAULT_REQUEST_LIMITS = RequestLimits(max_connections=100, max_keepalive_connections=20, keepalive_expiry=5)

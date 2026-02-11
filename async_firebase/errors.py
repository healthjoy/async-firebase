"""Async Firebase errors."""

import typing as t
from enum import Enum

import httpx


class FcmErrorCode(Enum):
    INVALID_ARGUMENT = "INVALID_ARGUMENT"
    FAILED_PRECONDITION = "FAILED_PRECONDITION"
    OUT_OF_RANGE = "OUT_OF_RANGE"
    UNAUTHENTICATED = "UNAUTHENTICATED"
    PERMISSION_DENIED = "PERMISSION_DENIED"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    ABORTED = "ABORTED"
    ALREADY_EXISTS = "ALREADY_EXISTS"
    RESOURCE_EXHAUSTED = "RESOURCE_EXHAUSTED"
    CANCELLED = "CANCELLED"
    DATA_LOSS = "DATA_LOSS"
    UNKNOWN = "UNKNOWN"
    INTERNAL = "INTERNAL"
    UNAVAILABLE = "UNAVAILABLE"
    DEADLINE_EXCEEDED = "DEADLINE_EXCEEDED"


class BaseAsyncFirebaseError(Exception):
    """Base error for Async Firebase"""


class AsyncFirebaseError(BaseAsyncFirebaseError):
    """A prototype for all AF Errors.

    This error and its subtypes and the reason to rise them are consistent with Google's errors,
    that may be found in `firebase-admin-python` in `firebase_admin.exceptions module`.

    Subclasses should set ``default_code`` to the appropriate ``FcmErrorCode`` value so that
    callers can omit the ``code`` parameter.
    """

    default_code: str = FcmErrorCode.UNKNOWN.value

    def __init__(
        self,
        message: str,
        *,
        code: t.Optional[str] = None,
        cause: t.Optional[httpx.HTTPError] = None,
        http_response: t.Optional[httpx.Response] = None,
    ):
        """Init the AsyncFirebase error.

        :param message: A human-readable error message string.
        :param code: A string error code that represents the type of the exception (optional).
            Defaults to the subclass's ``default_code``. Possible error codes are defined in
            https://cloud.google.com/apis/design/errors#handling_errors.
        :param cause: The exception that caused this error (optional).
        :param http_response: If this error was caused by an HTTP error response, this property is
            set to the ``httpx.Response`` object that represents the HTTP response (optional).
            See https://www.python-httpx.org/api/#response for details of this object.
        """
        self.code = code or self.default_code
        self.cause = cause
        self.http_response = http_response
        super().__init__(message)


class DeadlineExceededError(AsyncFirebaseError):
    """Request deadline exceeded.

    This will happen only if the caller sets a deadline that is shorter than the method's
    default deadline (i.e. requested deadline is not enough for the server to process the
    request) and the request did not finish within the deadline.
    """

    default_code = FcmErrorCode.DEADLINE_EXCEEDED.value


class UnavailableError(AsyncFirebaseError):
    """Service unavailable. Typically the server is down."""

    default_code = FcmErrorCode.UNAVAILABLE.value


class UnknownError(AsyncFirebaseError):
    """Unknown server error."""

    default_code = FcmErrorCode.UNKNOWN.value


class UnauthenticatedError(AsyncFirebaseError):
    """Request not authenticated due to missing, invalid, or expired OAuth token."""

    default_code = FcmErrorCode.UNAUTHENTICATED.value


class ThirdPartyAuthError(UnauthenticatedError):
    """APNs certificate or web push auth key was invalid or missing."""


class ResourceExhaustedError(AsyncFirebaseError):
    """Either out of resource quota or reaching rate limiting."""

    default_code = FcmErrorCode.RESOURCE_EXHAUSTED.value


class QuotaExceededError(ResourceExhaustedError):
    """Sending limit exceeded for the message target."""


class PermissionDeniedError(AsyncFirebaseError):
    """Client does not have sufficient permission.

    This can happen because the OAuth token does not have the right scopes, the client doesn't
    have permission, or the API has not been enabled for the client project.
    """

    default_code = FcmErrorCode.PERMISSION_DENIED.value


class SenderIdMismatchError(PermissionDeniedError):
    """The authenticated sender ID is different from the sender ID for the registration token."""


class NotFoundError(AsyncFirebaseError):
    """A specified resource is not found, or the request is rejected by undisclosed reasons.

    An example of the possible cause of this error is whitelisting.
    """

    default_code = FcmErrorCode.NOT_FOUND.value


class UnregisteredError(NotFoundError):
    """App instance was unregistered from FCM.

    This usually means that the token used is no longer valid and a new one must be used.
    """


class InvalidArgumentError(AsyncFirebaseError):
    """Client specified an invalid argument."""

    default_code = FcmErrorCode.INVALID_ARGUMENT.value


class FailedPreconditionError(AsyncFirebaseError):
    """Request can not be executed in the current system state, such as deleting a non-empty directory."""

    default_code = FcmErrorCode.FAILED_PRECONDITION.value


class OutOfRangeError(AsyncFirebaseError):
    """Client specified an invalid range."""

    default_code = FcmErrorCode.OUT_OF_RANGE.value


class AbortedError(AsyncFirebaseError):
    """Concurrency conflict, such as read-modify-write conflict."""

    default_code = FcmErrorCode.ABORTED.value


class AlreadyExistsError(AsyncFirebaseError):
    """The resource that a client tried to create already exists."""

    default_code = FcmErrorCode.ALREADY_EXISTS.value


class ConflictError(AsyncFirebaseError):
    """Concurrency conflict, such as read-modify-write conflict."""

    default_code = FcmErrorCode.CONFLICT.value


class CancelledError(AsyncFirebaseError):
    """Request cancelled by the client."""

    default_code = FcmErrorCode.CANCELLED.value


class DataLossError(AsyncFirebaseError):
    """Unrecoverable data loss or data corruption."""

    default_code = FcmErrorCode.DATA_LOSS.value


class InternalError(AsyncFirebaseError):
    """Internal server error."""

    default_code = FcmErrorCode.INTERNAL.value

"""Resolves HTTP outcomes into domain response objects.

All HTTP-to-domain-error resolution and response parsing lives here.
The three lookup dictionaries, resolution chain, and JSON parsing are
internal implementation details. Callers use the four typed public functions.
"""

import logging
import typing as t

import httpx

from async_firebase import errors
from async_firebase.errors import (
    AsyncFirebaseError,
    DeadlineExceededError,
    FcmErrorCode,
    QuotaExceededError,
    SenderIdMismatchError,
    ThirdPartyAuthError,
    UnavailableError,
    UnknownError,
    UnregisteredError,
)
from async_firebase.messages import FCMResponse, TopicManagementResponse


FCM_ERROR_TYPE_PREFIX = "type.googleapis.com/google.firebase.fcm.v1.FcmError"

_ERROR_CODE_TO_EXCEPTION_TYPE: t.Dict[str, t.Type[AsyncFirebaseError]] = {
    FcmErrorCode.INVALID_ARGUMENT.value: errors.InvalidArgumentError,
    FcmErrorCode.FAILED_PRECONDITION.value: errors.FailedPreconditionError,
    FcmErrorCode.OUT_OF_RANGE.value: errors.OutOfRangeError,
    FcmErrorCode.UNAUTHENTICATED.value: errors.UnauthenticatedError,
    FcmErrorCode.PERMISSION_DENIED.value: errors.PermissionDeniedError,
    FcmErrorCode.NOT_FOUND.value: errors.NotFoundError,
    FcmErrorCode.ABORTED.value: errors.AbortedError,
    FcmErrorCode.ALREADY_EXISTS.value: errors.AlreadyExistsError,
    FcmErrorCode.CONFLICT.value: errors.ConflictError,
    FcmErrorCode.RESOURCE_EXHAUSTED.value: errors.ResourceExhaustedError,
    FcmErrorCode.CANCELLED.value: errors.CancelledError,
    FcmErrorCode.DATA_LOSS.value: errors.DataLossError,
    FcmErrorCode.UNKNOWN.value: errors.UnknownError,
    FcmErrorCode.INTERNAL.value: errors.InternalError,
    FcmErrorCode.UNAVAILABLE.value: errors.UnavailableError,
    FcmErrorCode.DEADLINE_EXCEEDED.value: errors.DeadlineExceededError,
}

_HTTP_STATUS_TO_ERROR_CODE: t.Dict[int, str] = {
    400: FcmErrorCode.INVALID_ARGUMENT.value,
    401: FcmErrorCode.UNAUTHENTICATED.value,
    403: FcmErrorCode.PERMISSION_DENIED.value,
    404: FcmErrorCode.NOT_FOUND.value,
    409: FcmErrorCode.CONFLICT.value,
    412: FcmErrorCode.FAILED_PRECONDITION.value,
    429: FcmErrorCode.RESOURCE_EXHAUSTED.value,
    500: FcmErrorCode.INTERNAL.value,
    503: FcmErrorCode.UNAVAILABLE.value,
}

_FCM_ERROR_TYPES: t.Dict[str, t.Type[AsyncFirebaseError]] = {
    "APNS_AUTH_ERROR": ThirdPartyAuthError,
    "QUOTA_EXCEEDED": QuotaExceededError,
    "SENDER_ID_MISMATCH": SenderIdMismatchError,
    "THIRD_PARTY_AUTH_ERROR": ThirdPartyAuthError,
    "UNREGISTERED": UnregisteredError,
}


def _parse_platform_error(response: httpx.Response) -> dict:
    """Extract the code and message from GCP API Error HTTP response."""
    data: dict = {}
    try:
        data = response.json()
    except ValueError:
        logging.getLogger(__name__).warning(
            "Failed to parse JSON from error response (status %s): %r",
            response.status_code,
            response.content,
        )

    error_data = data.get("error", {})
    if not error_data.get("message"):
        error_data["message"] = (
            f"Unexpected HTTP response with status: {response.status_code}; body: {response.content!r}"
        )
    return error_data


def _get_fcm_error_type(error_data: dict) -> t.Optional[t.Type[AsyncFirebaseError]]:
    if not error_data:
        return None

    fcm_code = None
    for detail in error_data.get("details", []):
        if detail.get("@type") == FCM_ERROR_TYPE_PREFIX:
            fcm_code = detail.get("errorCode")
            break

    if not fcm_code:
        return None

    return _FCM_ERROR_TYPES.get(fcm_code)


def _handle_fcm_error(error: httpx.HTTPStatusError) -> t.Optional[AsyncFirebaseError]:
    error_data = _parse_platform_error(error.response)
    err_type = _get_fcm_error_type(error_data)
    return err_type(error_data["message"], cause=error, http_response=error.response) if err_type else None


def _get_error_by_status_code(error: httpx.HTTPStatusError) -> AsyncFirebaseError:
    error_data = _parse_platform_error(error.response)
    code = error_data.get(
        "status", _HTTP_STATUS_TO_ERROR_CODE.get(error.response.status_code, FcmErrorCode.UNKNOWN.value)
    )
    err_type = _ERROR_CODE_TO_EXCEPTION_TYPE.get(code, errors.UnknownError)
    return err_type(message=error_data["message"], cause=error, http_response=error.response)


def _handle_request_error(error: httpx.HTTPError) -> AsyncFirebaseError:
    if isinstance(error, httpx.TimeoutException):
        return DeadlineExceededError(message=f"Timed out while making an API call: {error}", cause=error)
    elif isinstance(error, httpx.ConnectError):
        return UnavailableError(message=f"Failed to establish a connection: {error}", cause=error)
    elif not hasattr(error, "response"):
        return UnknownError(message=f"Unknown error while making a remote service call: {error}", cause=error)

    return _get_error_by_status_code(t.cast(httpx.HTTPStatusError, error))


def _resolve_exception(error: httpx.HTTPError) -> AsyncFirebaseError:
    """Resolve an httpx error into the appropriate AsyncFirebaseError."""
    if isinstance(error, httpx.HTTPStatusError):
        fcm_error = _handle_fcm_error(error)
        if fcm_error:
            return fcm_error
        return _handle_request_error(error)

    if isinstance(error, httpx.HTTPError):
        return _handle_request_error(error)

    return AsyncFirebaseError(
        "Unexpected error has happened when hitting the FCM API",
        code=FcmErrorCode.UNKNOWN.value,
        cause=error,
    )


# ── Public API: 4 typed functions ──────────────────────────────────


def handle_fcm_response(response: httpx.Response) -> FCMResponse:
    """Turn a successful httpx.Response into an FCMResponse."""
    return FCMResponse(fcm_response=response.json())


def handle_fcm_error(error: httpx.HTTPError) -> FCMResponse:
    """Turn any httpx error into an FCMResponse (with .exception set)."""
    return FCMResponse(exception=_resolve_exception(error))


def handle_topic_response(response: httpx.Response) -> TopicManagementResponse:
    """Turn a successful httpx.Response into a TopicManagementResponse."""
    return TopicManagementResponse(response)


def handle_topic_error(error: httpx.HTTPError) -> TopicManagementResponse:
    """Turn any httpx error into a TopicManagementResponse (with .exception set)."""
    return TopicManagementResponse(exception=_resolve_exception(error))


# ── Backward-compatible handler classes ────────────────────────────
# These exist so that external code importing FCMResponseHandler /
# TopicManagementResponseHandler continues to work.


class FCMResponseHandler:
    def handle_response(self, response):
        return handle_fcm_response(response)

    def handle_error(self, error):
        return handle_fcm_error(error)

    @staticmethod
    def _get_fcm_error_type(error_data):
        return _get_fcm_error_type(error_data)


class TopicManagementResponseHandler:
    def handle_response(self, response):
        return handle_topic_response(response)

    def handle_error(self, error):
        return handle_topic_error(error)

    @staticmethod
    def _get_fcm_error_type(error_data):
        return _get_fcm_error_type(error_data)

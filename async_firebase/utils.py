import logging
import typing as t
from abc import ABC, abstractmethod
from copy import deepcopy
from dataclasses import fields, is_dataclass
from enum import Enum
from urllib.parse import quote, urlencode, urljoin

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
from async_firebase.messages import FCMBatchResponse, FCMResponse, TopicManagementResponse


FCM_ERROR_TYPE_PREFIX = "type.googleapis.com/google.firebase.fcm.v1.FcmError"


def join_url(
    base: str,
    *parts: t.Union[str, int],
    params: t.Optional[dict] = None,
    leading_slash: bool = False,
    trailing_slash: bool = False,
) -> str:
    """Construct a full ("absolute") URL by combining a "base URL" (base) with another URL (url) parts.

    :param base: base URL part
    :param parts: another url parts that should be joined
    :param params: dict with query params
    :param leading_slash: flag to force leading slash
    :param trailing_slash: flag to force trailing slash

    :return: full URL
    """
    url = base
    if parts:
        quoted_and_stripped_parts = [quote(str(part).strip("/"), safe=": /") for part in parts]
        url = "/".join([base.strip("/"), *quoted_and_stripped_parts])

    # trailing slash can be important
    if trailing_slash:
        url = f"{url}/"
    # as well as a leading slash
    if leading_slash:
        url = f"/{url}"

    if params:
        url = urljoin(url, f"?{urlencode(params)}")

    return url


def remove_null_values(dict_value: t.Dict[str, t.Any]) -> t.Dict[str, t.Any]:
    """Remove Falsy values from the dictionary."""
    return {k: v for k, v in dict_value.items() if v is not None and v != [] and v != {}}


def cleanup_firebase_message(dataclass_obj, dict_factory: t.Callable = dict) -> dict:
    """
    The instrumentation to cleanup firebase message from null values.

    Example::

        considering following dataclass

        msg = Message(
            token='qwe',
            data={},
            notification=Notification(title='push-title', body='push-body'),
            android=None,
            webpush={},
            apns=APNSConfig(
                headers={'hdr': 'qwe'},
                payload=APNSPayload(
                    aps=Aps(
                        alert=None,
                        badge=None,
                        sound='generic',
                        content_available=None,
                        category=None,
                        thread_id=None,
                        mutable_content=None,
                        custom_data={}
                    ),
                    custom_data={}
                )
            ),
            topic=None,
            condition=None
        )

        >>> dataclass_to_dict_remove_null_values(msg)
        {
            'token': 'qwe',
            'notification': {'title': 'push-title', 'body': 'push-body'},
            'apns': {
                'headers': {'hdr': 'qwe'},
                'payload': {
                    'aps': {'sound': 'generic'}
                }
            }
        }

    :param dataclass_obj: instance of dataclass. This suppose to be instance of ``messages.PushNotification`` or
        ``messages.Message``.
    :param dict_factory: if given, ``dict_factory`` will be used instead of built-in dict.
        The function applies recursively to field values that are dataclass instances.
    :return: the fields of a dataclass instance as a new dictionary mapping field names to field values.
    """
    if is_dataclass(dataclass_obj):
        result = []
        for f in fields(dataclass_obj):
            value = cleanup_firebase_message(getattr(dataclass_obj, f.name), dict_factory)
            if isinstance(value, Enum):
                value = value.value
            result.append((f.name, value))
        return remove_null_values(dict_factory(result))
    elif isinstance(dataclass_obj, (list, tuple)):
        return type(dataclass_obj)(cleanup_firebase_message(v, dict_factory) for v in dataclass_obj)  # type: ignore
    elif isinstance(dataclass_obj, dict):
        return remove_null_values({k: cleanup_firebase_message(v, dict_factory) for k, v in dataclass_obj.items()})
    return deepcopy(dataclass_obj)


FCMResponseType = t.TypeVar("FCMResponseType", FCMResponse, FCMBatchResponse, TopicManagementResponse)


class FCMResponseHandlerBase(ABC, t.Generic[FCMResponseType]):
    ERROR_CODE_TO_EXCEPTION_TYPE: t.Dict[str, t.Type[AsyncFirebaseError]] = {
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

    HTTP_STATUS_TO_ERROR_CODE = {
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

    FCM_ERROR_TYPES = {
        "APNS_AUTH_ERROR": ThirdPartyAuthError,
        "QUOTA_EXCEEDED": QuotaExceededError,
        "SENDER_ID_MISMATCH": SenderIdMismatchError,
        "THIRD_PARTY_AUTH_ERROR": ThirdPartyAuthError,
        "UNREGISTERED": UnregisteredError,
    }

    @abstractmethod
    def handle_response(self, response: httpx.Response) -> FCMResponseType:
        pass

    @abstractmethod
    def handle_error(self, error: httpx.HTTPError) -> FCMResponseType:
        pass

    @staticmethod
    def _handle_response(response: httpx.Response) -> FCMResponse:
        return FCMResponse(fcm_response=response.json())

    def _resolve_exception(self, error: httpx.HTTPError) -> AsyncFirebaseError:
        """Resolve an httpx error into the appropriate AsyncFirebaseError."""
        if isinstance(error, httpx.HTTPStatusError):
            fcm_error = self._handle_fcm_error(error)
            if fcm_error:
                return fcm_error
            return self._handle_request_error(error)

        if isinstance(error, httpx.HTTPError):
            return self._handle_request_error(error)

        return AsyncFirebaseError(
            "Unexpected error has happened when hitting the FCM API",
            code=FcmErrorCode.UNKNOWN.value,
            cause=error,
        )

    def _handle_error(self, error: httpx.HTTPError) -> FCMResponse:
        return FCMResponse(exception=self._resolve_exception(error))

    def _handle_request_error(self, error: httpx.HTTPError):
        if isinstance(error, httpx.TimeoutException):
            return DeadlineExceededError(message=f"Timed out while making an API call: {error}", cause=error)
        elif isinstance(error, httpx.ConnectError):
            return UnavailableError(message=f"Failed to establish a connection: {error}", cause=error)
        elif not hasattr(error, "response"):
            return UnknownError(message=f"Unknown error while making a remote service call: {error}", cause=error)

        return self._get_error_by_status_code(t.cast(httpx.HTTPStatusError, error))

    def _get_error_by_status_code(self, error: httpx.HTTPStatusError):
        error_data = self._parse_platform_error(error.response)
        code = error_data.get("status", self._http_status_to_error_code(error.response.status_code))
        err_type = self._error_code_to_exception_type(code)
        return err_type(message=error_data["message"], cause=error, http_response=error.response)  # type: ignore

    def _handle_fcm_error(self, error: httpx.HTTPStatusError):
        error_data = self._parse_platform_error(error.response)
        err_type = self._get_fcm_error_type(error_data)
        return err_type(error_data["message"], cause=error, http_response=error.response) if err_type else None

    @classmethod
    def _http_status_to_error_code(cls, http_status_code: int) -> str:
        return cls.HTTP_STATUS_TO_ERROR_CODE.get(http_status_code, FcmErrorCode.UNKNOWN.value)

    @classmethod
    def _error_code_to_exception_type(cls, error_code: str) -> t.Type[AsyncFirebaseError]:
        return cls.ERROR_CODE_TO_EXCEPTION_TYPE.get(error_code, errors.UnknownError)

    @classmethod
    def _get_fcm_error_type(cls, error_data: dict):
        if not error_data:
            return None

        fcm_code = None
        for detail in error_data.get("details", []):
            if detail.get("@type") == FCM_ERROR_TYPE_PREFIX:
                fcm_code = detail.get("errorCode")
                break

        if not fcm_code:
            return None

        return cls.FCM_ERROR_TYPES.get(fcm_code)

    @staticmethod
    def _parse_platform_error(response: httpx.Response):
        """Extract the code and mesage from GCP API Error HTTP response."""
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


class FCMResponseHandler(FCMResponseHandlerBase[FCMResponse]):
    def handle_error(self, error: httpx.HTTPError) -> FCMResponse:
        return self._handle_error(error)

    def handle_response(self, response: httpx.Response) -> FCMResponse:
        return self._handle_response(response)


class TopicManagementResponseHandler(FCMResponseHandlerBase[TopicManagementResponse]):
    def handle_error(self, error: httpx.HTTPError) -> TopicManagementResponse:
        return TopicManagementResponse(exception=self._resolve_exception(error))

    def handle_response(self, response: httpx.Response) -> TopicManagementResponse:
        return TopicManagementResponse(response)

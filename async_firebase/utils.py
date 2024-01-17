import io
import json
import typing as t
from abc import ABC, abstractmethod
from copy import deepcopy
from dataclasses import fields, is_dataclass
from email.generator import Generator
from email.mime.multipart import MIMEMultipart
from email.mime.nonmultipart import MIMENonMultipart
from email.parser import FeedParser
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
from async_firebase.messages import FCMBatchResponse, FCMResponse


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
        url = "/".join([base.strip("/"), quote("/".join(map(lambda x: str(x).strip("/"), parts)))])

    # trailing slash can be important
    if trailing_slash:
        url = f"{url}/"
    # as well as a leading slash
    if leading_slash:
        url = f"/{url}"

    if params:
        url = urljoin(url, "?{}".format(urlencode(params)))

    return url


def remove_null_values(dict_value: t.Dict[str, t.Any]) -> t.Dict[str, t.Any]:
    """Remove Falsy values from the dictionary."""
    return {k: v for k, v in dict_value.items() if v not in [None, [], {}]}


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
            result.append((f.name, value))
        return remove_null_values(dict_factory(result))
    elif isinstance(dataclass_obj, (list, tuple)):
        return type(dataclass_obj)(cleanup_firebase_message(v, dict_factory) for v in dataclass_obj)  # type: ignore
    elif isinstance(dataclass_obj, dict):
        return remove_null_values({k: cleanup_firebase_message(v, dict_factory) for k, v in dataclass_obj.items()})
    return deepcopy(dataclass_obj)


def serialize_mime_message(
    message: t.Union[MIMEMultipart, MIMENonMultipart],
    mangle_from: t.Optional[bool] = None,
    max_header_len: t.Optional[int] = None,
) -> str:
    """
    Serialize the MIME type message.

    :param message: MIME type message
    :param mangle_from: is a flag that, when True (the default if policy
        is not set), escapes From_ lines in the body of the message by putting
        a `>' in front of them.
    :param max_header_len: specifies the longest length for a non-continued
        header.  When a header line is longer (in characters, with tabs
        expanded to 8 spaces) than max_header_len, the header will split as
        defined in the Header class.  Set max_header_len to zero to disable
        header wrapping. The default is 78, as recommended (but not required)
        by RFC 2822.
    :return: the entire contents of the object.
    """
    fp = io.StringIO()
    gen = Generator(fp, mangle_from_=mangle_from, maxheaderlen=max_header_len)
    gen.flatten(message, unixfrom=False)
    return fp.getvalue()


FCMResponseType = t.TypeVar("FCMResponseType", FCMResponse, FCMBatchResponse)


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

    def _handle_error(self, error: httpx.HTTPError) -> FCMResponse:
        exc = (
            (isinstance(error, httpx.HTTPStatusError) and self._handle_fcm_error(error))
            or (isinstance(error, httpx.HTTPError) and self._handle_request_error(error))
            or AsyncFirebaseError(
                code=FcmErrorCode.UNKNOWN.value,
                message="Unexpected error has happened when hitting the FCM API",
                cause=error,
            )
        )
        return FCMResponse(exception=exc)

    def _handle_request_error(self, error: httpx.HTTPError):
        if isinstance(error, httpx.TimeoutException):
            return DeadlineExceededError(message=f"Timed out while making an API call: {error}", cause=error)
        elif isinstance(error, httpx.ConnectError):
            return UnavailableError(message=f"Failed to establish a connection: {error}", cause=error)
        elif not hasattr(error, "response"):
            return UnknownError(message="Unknown error while making a remote service call: {error}", cause=error)

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
            if detail.get("@type") == "type.googleapis.com/google.firebase.fcm.v1.FcmError":
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
            pass

        error_data = data.get("error", {})
        if not error_data.get("message"):
            error_data[
                "message"
            ] = f"Unexpected HTTP response with status: {response.status_code}; body: {response.content!r}"
        return error_data


class FCMResponseHandler(FCMResponseHandlerBase[FCMResponse]):
    def handle_error(self, error: httpx.HTTPError) -> FCMResponse:
        return self._handle_error(error)

    def handle_response(self, response: httpx.Response) -> FCMResponse:
        return self._handle_response(response)


class FCMBatchResponseHandler(FCMResponseHandlerBase[FCMBatchResponse]):
    def handle_error(self, error: httpx.HTTPError):
        fcm_response = self._handle_error(error)
        return FCMBatchResponse(responses=[fcm_response])

    def handle_response(self, response: httpx.Response):
        fcm_push_responses = []
        responses = self._deserialize_batch_response(response)
        for single_resp in responses:
            if single_resp.status_code >= 300:
                exc = httpx.HTTPStatusError("FCM Error", response=single_resp, request=response.request)
                fcm_push_responses.append(self._handle_error(exc))
            else:
                fcm_push_responses.append(self._handle_response(single_resp))

        return FCMBatchResponse(responses=fcm_push_responses)

    @staticmethod
    def _deserialize_batch_response(response: httpx.Response) -> t.List[httpx.Response]:
        """Convert batch response into list of `httpx.Response` responses for each multipart.

        :param response: string, headers and body as a string.
        :return: list of `httpx.Response` responses.
        """
        # Prepend with a content-type header so FeedParser can handle it.
        header = f"content-type: {response.headers['content-type']}\r\n\r\n"
        # PY3's FeedParser only accepts unicode. So we should decode content here, and encode each payload again.
        content = response.content.decode()
        for_parser = f"{header}{content}"

        parser = FeedParser()
        parser.feed(for_parser)
        mime_response = parser.close()

        if not mime_response.is_multipart():
            raise ValueError("Response not in multipart/mixed format.")

        responses = []
        for part in mime_response.get_payload():
            request_id = part["Content-ID"].split("-", 1)[-1]
            status_line, payload = part.get_payload().split("\n", 1)
            _, status_code, _ = status_line.split(" ", 2)
            status_code = int(status_code)

            # Parse the rest of the response
            parser = FeedParser()
            parser.feed(payload)
            msg = parser.close()
            msg["status_code"] = status_code

            # Create httpx.Response from the parsed headers.
            resp = httpx.Response(
                status_code=status_code,
                headers=httpx.Headers({"Content-Type": msg.get_content_type(), "X-Request-ID": request_id}),
                content=msg.get_payload(),
                json=json.loads(msg.get_payload()),
            )
            responses.append(resp)

        return responses

import io
import typing as t
from abc import ABC, abstractmethod
from copy import deepcopy
from dataclasses import fields, is_dataclass
from email.generator import Generator
from email.mime.multipart import MIMEMultipart
from email.mime.nonmultipart import MIMENonMultipart

import httpx

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
from async_firebase.messages import FcmPushMulticastResponse, FcmPushResponse


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
    message: t.Union[MIMEMultipart, MIMENonMultipart], mangle_from: bool = None, max_header_len: int = None
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


FcmResponse = t.TypeVar('FcmResponse', FcmPushResponse, FcmPushMulticastResponse)


class FcmResponseHandler(ABC, t.Generic[FcmResponse]):

    FCM_ERROR_TYPES = {
        'APNS_AUTH_ERROR': ThirdPartyAuthError,
        'QUOTA_EXCEEDED': QuotaExceededError,
        'SENDER_ID_MISMATCH': SenderIdMismatchError,
        'THIRD_PARTY_AUTH_ERROR': ThirdPartyAuthError,
        'UNREGISTERED': UnregisteredError,
    }

    @abstractmethod
    def handle_error(self, error: httpx.HTTPError) -> FcmResponse:
        pass

    def _handle_request_error(self, error: httpx.RequestError):
        if isinstance(error, httpx.TimeoutException):
            return DeadlineExceededError(message=f"Timed out while making an API call: {error}", cause=error)
        elif isinstance(error, httpx.ConnectError):
            return UnavailableError(message=f"Failed to establish a connection: {error}", cause=error)
        else:
            return UnknownError(message="Unknown error while making a remote service call: {error}", cause=error)

    def _handle_fcm_error(self, error: httpx.HTTPStatusError):
        error_data = self._parse_platform_error(error.response)
        exc_type = self._get_fcm_error_type(error_data)
        return exc_type(error_data["message"], cause=error, http_response=error.response) if exc_type else None

    @classmethod
    def _get_fcm_error_type(cls, error_data: dict):
        if not error_data:
            return None

        fcm_code = None
        for detail in error_data.get('details', []):
            if detail.get('@type') == 'type.googleapis.com/google.firebase.fcm.v1.FcmError':
                fcm_code = detail.get('errorCode')
                break

        if not fcm_code:
            return None

        return cls.FCM_ERROR_TYPES.get(fcm_code)

    def _parse_platform_error(self, response: httpx.Response):
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

    @abstractmethod
    def handle_response(self, response: httpx.Response) -> FcmResponse:
        pass


class FcmPushResponseHandler(FcmResponseHandler[FcmPushResponse]):
    def handle_error(self, error: httpx.HTTPError) -> FcmPushResponse:
        exc = None
        if isinstance(error, httpx.RequestError):
            exc = self._handle_request_error(error)
        elif isinstance(error, httpx.HTTPStatusError):
            exc = self._handle_fcm_error(error)

        if exc is None:
            exc = AsyncFirebaseError(
                code=FcmErrorCode.UNKNOWN.value,
                message="Unexpected error has happened when hitting the FCM API",
                cause=error,
            )
        return FcmPushResponse(exception=exc)

    def handle_response(self, response: httpx.Response) -> FcmPushResponse:
        return FcmPushResponse(fcm_response=response.json())


class FcmPushMulticastResponseHandler(FcmResponseHandler[FcmPushMulticastResponse]):
    def handle_error(self):
        pass

    def handle_response(self):
        pass

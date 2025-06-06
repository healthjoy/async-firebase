"""
The module houses client to communicate with FCM - Firebase Cloud Messaging (Android, iOS and Web).

Documentation for google-auth package https://google-auth.readthedocs.io/en/latest/user-guide.html that is used
to authorize request which is being made to Firebase.
"""

import logging
import typing as t
import uuid
from datetime import datetime, timedelta, timezone
from email.mime.nonmultipart import MIMENonMultipart
from importlib.metadata import version
from pathlib import PurePath
from urllib.parse import urlencode

import httpx
from google.oauth2 import service_account  # type: ignore

from async_firebase._config import DEFAULT_REQUEST_LIMITS, DEFAULT_REQUEST_TIMEOUT, RequestLimits, RequestTimeout
from async_firebase.messages import FCMBatchResponse, FCMResponse, TopicManagementResponse
from async_firebase.utils import (
    FCMBatchResponseHandler,
    FCMResponseHandler,
    TopicManagementResponseHandler,
    join_url,
    serialize_mime_message,
)


class AsyncClientBase:
    """Base asynchronous client"""

    BASE_URL: str = "https://fcm.googleapis.com"
    TOKEN_URL: str = "https://oauth2.googleapis.com/token"
    FCM_ENDPOINT: str = "/v1/projects/{project_id}/messages:send"
    FCM_BATCH_ENDPOINT: str = "/batch"
    # A list of accessible OAuth 2.0 scopes can be found https://developers.google.com/identity/protocols/oauth2/scopes.
    SCOPES: t.List[str] = [
        "https://www.googleapis.com/auth/cloud-platform",
    ]
    IID_URL = "https://iid.googleapis.com"
    IID_HEADERS = {"access_token_auth": "true"}
    TOPIC_ADD_ACTION = "iid/v1:batchAdd"
    TOPIC_REMOVE_ACTION = "iid/v1:batchRemove"

    def __init__(
        self,
        credentials: t.Optional[service_account.Credentials] = None,
        scopes: t.Optional[t.List[str]] = None,
        *,
        request_timeout: RequestTimeout = DEFAULT_REQUEST_TIMEOUT,
        request_limits: RequestLimits = DEFAULT_REQUEST_LIMITS,
        use_http2: bool = False,
    ) -> None:
        """
        :param credentials: instance of ``google.oauth2.service_account.Credentials``.
            Usually, you'll create these credentials with one of the helper constructors. To create credentials using a
            Google service account private key JSON file::

                self.creds_from_service_account_file('service-account.json')

            Or if you already have the service account file loaded::

                service_account_info = json.load(open('service_account.json'))
                self.creds_from_service_account_info(service_account_info)

        :param scopes: user-defined scopes to request during the authorization grant.
        :param request_timeout: advanced feature that allows to change request timeout.
        :param request_limits: advanced feature that allows to control the connection pool size.
        :param use_http2: advanced feature that allows to control usage of http protocol.
        """
        self._credentials: service_account.Credentials = credentials
        self.scopes: t.List[str] = scopes or self.SCOPES

        self._request_timeout = request_timeout
        self._request_limits = request_limits
        self._use_http2 = use_http2
        self._http_client: t.Optional[httpx.AsyncClient] = None

    @property
    def _client(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(**self._request_timeout.__dict__),
                limits=httpx.Limits(**self._request_limits.__dict__),
                http2=self._use_http2,
            )
        return self._http_client

    def creds_from_service_account_info(self, service_account_info: t.Dict[str, str]) -> None:
        """
        Creates a Credentials instance from parsed service account info.

        :param service_account_info: the service account info in Google format.
        """
        self._credentials = service_account.Credentials.from_service_account_info(
            info=service_account_info, scopes=self.scopes
        )

    def creds_from_service_account_file(self, service_account_filename: t.Union[str, PurePath]) -> None:
        """
        Creates a Credentials instance from a service account json file.

        :param service_account_filename: the path to the service account json file.
        """
        if isinstance(service_account_filename, PurePath):
            service_account_filename = str(service_account_filename)

        logging.debug("Creating credentials from file: %s", service_account_filename)
        self._credentials = service_account.Credentials.from_service_account_file(
            filename=service_account_filename, scopes=self.scopes
        )

    async def _get_access_token(self) -> str:
        """Get OAuth 2 access token."""
        if self._credentials.valid:
            return self._credentials.token

        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = urlencode(
            {
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": self._credentials._make_authorization_grant_assertion(),
            }
        ).encode("utf-8")

        response: httpx.Response = await self._client.post(self.TOKEN_URL, content=data, headers=headers)
        response_data = response.json()

        self._credentials.expiry = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(
            seconds=response_data["expires_in"]
        )
        self._credentials.token = response_data["access_token"]
        return self._credentials.token

    @staticmethod
    def get_request_id():
        """Generate unique request ID."""
        return str(uuid.uuid4())

    @staticmethod
    def serialize_batch_request(request: httpx.Request) -> str:
        """
        Convert an HttpRequest object into a string.

        :param request: `httpx.Request`, the request to serialize.
        :return: a string in application/http format.
        """
        status_line = f"{request.method} {request.url.path} HTTP/1.1\n"
        major, minor = request.headers.get("content-type", "application/json").split("/")
        msg = MIMENonMultipart(major, minor)
        headers = request.headers.copy()

        # MIMENonMultipart adds its own Content-Type header.
        if "content-type" in headers:
            del headers["content-type"]

        for key, value in headers.items():
            msg[key] = value
        msg.set_unixfrom(None)  # type: ignore

        if request.content is not None:
            msg.set_payload(request.content)
            msg["content-length"] = str(len(request.content))

        body = serialize_mime_message(msg, max_header_len=0)
        return f"{status_line}{body}"

    async def prepare_headers(self) -> t.Dict[str, str]:
        """Prepare HTTP headers that will be used to request Firebase Cloud Messaging."""
        logging.debug("Preparing HTTP headers for all the subsequent requests")
        access_token: str = await self._get_access_token()
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; UTF-8",
            "X-Request-Id": self.get_request_id(),
            "X-GOOG-API-FORMAT-VERSION": "2",
            "X-FIREBASE-CLIENT": "async-firebase/{0}".format(version("async-firebase")),
        }

    async def _send_request(
        self,
        url: str,
        response_handler: t.Union[FCMResponseHandler, FCMBatchResponseHandler, TopicManagementResponseHandler],
        json_payload: t.Optional[t.Dict[str, t.Any]] = None,
        headers: t.Optional[t.Dict[str, str]] = None,
        content: t.Union[str, bytes, t.Iterable[bytes], t.AsyncIterable[bytes], None] = None,
    ) -> t.Union[FCMResponse, FCMBatchResponse, TopicManagementResponse]:
        logging.debug(
            "Requesting POST %s, payload: %s, content: %s, headers: %s",
            url,
            json_payload,
            content,
            headers,
        )
        try:
            raw_fcm_response: httpx.Response = await self._client.post(
                url,
                json=json_payload,
                headers=headers or await self.prepare_headers(),
                content=content,
            )
            raw_fcm_response.raise_for_status()
        except httpx.HTTPError as exc:
            response = response_handler.handle_error(exc)
        else:
            logging.debug(
                "Response Code: %s, Time spent to make a request: %s",
                raw_fcm_response.status_code,
                raw_fcm_response.elapsed,
            )
            response = response_handler.handle_response(raw_fcm_response)

        return response

    async def send_request(
        self,
        uri: str,
        response_handler: t.Union[FCMResponseHandler, FCMBatchResponseHandler],
        json_payload: t.Optional[t.Dict[str, t.Any]] = None,
        headers: t.Optional[t.Dict[str, str]] = None,
        content: t.Union[str, bytes, t.Iterable[bytes], t.AsyncIterable[bytes], None] = None,
    ) -> t.Union[FCMResponse, FCMBatchResponse]:
        """
        Sends an HTTP call using the ``httpx`` library to FCM.

        :param uri: URI to be requested.
        :param response_handler: the model to handle response.
        :param json_payload: request JSON payload
        :param headers: request headers.
        :param content: request content
        :return: HTTP response
        """
        url = join_url(self.BASE_URL, uri)
        return await self._send_request(  # type: ignore
            url=url, response_handler=response_handler, json_payload=json_payload, headers=headers, content=content
        )

    async def send_iid_request(
        self,
        uri: str,
        response_handler: TopicManagementResponseHandler,
        json_payload: t.Optional[t.Dict[str, t.Any]] = None,
        headers: t.Optional[t.Dict[str, str]] = None,
        content: t.Union[str, bytes, t.Iterable[bytes], t.AsyncIterable[bytes], None] = None,
    ) -> TopicManagementResponse:
        """
        Sends an HTTP call using the ``httpx`` library to the IID service for topic management functionality.

        :param uri: URI to be requested.
        :param response_handler: the model to handle response.
        :param json_payload: request JSON payload
        :param headers: request headers.
        :param content: request content
        :return: HTTP response
        """
        url = join_url(self.IID_URL, uri)
        headers = headers or await self.prepare_headers()
        headers.update(self.IID_HEADERS)
        return await self._send_request(  # type: ignore
            url=url, response_handler=response_handler, json_payload=json_payload, headers=headers, content=content
        )

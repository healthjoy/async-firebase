"""
The module houses client to communicate with FCM - Firebase Cloud Messaging (Android, iOS and Web).

Documentation for google-auth package https://google-auth.readthedocs.io/en/latest/user-guide.html that is used
to authorize request which is being made to Firebase.
"""

import logging
import typing as t
import uuid
from importlib.metadata import version
from pathlib import PurePath

import httpx
from google.oauth2 import service_account  # type: ignore

from async_firebase._config import DEFAULT_REQUEST_LIMITS, DEFAULT_REQUEST_TIMEOUT, RequestLimits, RequestTimeout
from async_firebase._credentials import CredentialManager
from async_firebase.messages import FCMResponse, TopicManagementResponse
from async_firebase.responses import (
    handle_fcm_error,
    handle_fcm_response,
    handle_topic_error,
    handle_topic_response,
)
from async_firebase.utils import join_url


class AsyncClientBase:
    """Base asynchronous client"""

    BASE_URL: str = "https://fcm.googleapis.com"
    FCM_ENDPOINT: str = "/v1/projects/{project_id}/messages:send"
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
        self._credential_manager = CredentialManager(credentials=credentials, scopes=scopes)

        self._request_timeout = request_timeout
        self._request_limits = request_limits
        self._use_http2 = use_http2
        self._http_client: t.Optional[httpx.AsyncClient] = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
        return False

    async def close(self) -> None:
        """Close the underlying HTTP client and release resources."""
        if self._http_client is not None and not self._http_client.is_closed:
            await self._http_client.aclose()
            self._http_client = None

    @property
    def _client(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(**self._request_timeout.__dict__),
                limits=httpx.Limits(**self._request_limits.__dict__),
                http2=self._use_http2,
            )
        return self._http_client

    @property
    def _credentials(self) -> service_account.Credentials:
        return self._credential_manager.credentials

    def creds_from_service_account_info(self, service_account_info: t.Dict[str, str]) -> None:
        """
        Creates a Credentials instance from parsed service account info.

        :param service_account_info: the service account info in Google format.
        """
        self._credential_manager.from_service_account_info(service_account_info)

    def creds_from_service_account_file(self, service_account_filename: t.Union[str, PurePath]) -> None:
        """
        Creates a Credentials instance from a service account json file.

        :param service_account_filename: the path to the service account json file.
        """
        self._credential_manager.from_service_account_file(service_account_filename)

    async def _get_access_token(self) -> str:
        """Get OAuth 2 access token."""
        return await self._credential_manager.get_access_token(self._client)

    @staticmethod
    def get_request_id():
        """Generate unique request ID."""
        return str(uuid.uuid4())

    async def prepare_headers(self) -> t.Dict[str, str]:
        """Prepare HTTP headers that will be used to request Firebase Cloud Messaging."""
        logging.debug("Preparing HTTP headers for all the subsequent requests")
        access_token: str = await self._get_access_token()
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; UTF-8",
            "X-Request-Id": self.get_request_id(),
            "X-GOOG-API-FORMAT-VERSION": "2",
            "X-FIREBASE-CLIENT": f"async-firebase/{version('async-firebase')}",
        }

    async def _send_fcm_request(
        self,
        url: str,
        json_payload: t.Optional[t.Dict[str, t.Any]] = None,
        headers: t.Optional[t.Dict[str, str]] = None,
        content: t.Union[str, bytes, t.Iterable[bytes], t.AsyncIterable[bytes], None] = None,
    ) -> FCMResponse:
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
            return handle_fcm_error(exc)
        else:
            logging.debug(
                "Response Code: %s, Time spent to make a request: %s",
                raw_fcm_response.status_code,
                raw_fcm_response.elapsed,
            )
            return handle_fcm_response(raw_fcm_response)

    async def _send_topic_request(
        self,
        url: str,
        json_payload: t.Optional[t.Dict[str, t.Any]] = None,
        headers: t.Optional[t.Dict[str, str]] = None,
        content: t.Union[str, bytes, t.Iterable[bytes], t.AsyncIterable[bytes], None] = None,
    ) -> TopicManagementResponse:
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
            return handle_topic_error(exc)
        else:
            logging.debug(
                "Response Code: %s, Time spent to make a request: %s",
                raw_fcm_response.status_code,
                raw_fcm_response.elapsed,
            )
            return handle_topic_response(raw_fcm_response)

    async def send_fcm_request(
        self,
        uri: str,
        json_payload: t.Optional[t.Dict[str, t.Any]] = None,
        headers: t.Optional[t.Dict[str, str]] = None,
        content: t.Union[str, bytes, t.Iterable[bytes], t.AsyncIterable[bytes], None] = None,
        *,
        base_url: t.Optional[str] = None,
        extra_headers: t.Optional[t.Dict[str, str]] = None,
    ) -> FCMResponse:
        """
        Sends an HTTP call to FCM using the ``httpx`` library.

        :param uri: URI to be requested.
        :param json_payload: request JSON payload
        :param headers: request headers.
        :param content: request content
        :param base_url: base URL to use (defaults to FCM BASE_URL).
        :param extra_headers: additional headers to merge into the request headers.
        :return: FCMResponse
        """
        url = join_url(base_url or self.BASE_URL, uri)
        if extra_headers:
            headers = headers or await self.prepare_headers()
            headers.update(extra_headers)
        return await self._send_fcm_request(url=url, json_payload=json_payload, headers=headers, content=content)

    async def send_topic_request(
        self,
        uri: str,
        json_payload: t.Optional[t.Dict[str, t.Any]] = None,
        headers: t.Optional[t.Dict[str, str]] = None,
        content: t.Union[str, bytes, t.Iterable[bytes], t.AsyncIterable[bytes], None] = None,
        *,
        base_url: t.Optional[str] = None,
        extra_headers: t.Optional[t.Dict[str, str]] = None,
    ) -> TopicManagementResponse:
        """
        Sends an HTTP call to the IID service for topic management.

        :param uri: URI to be requested.
        :param json_payload: request JSON payload
        :param headers: request headers.
        :param content: request content
        :param base_url: base URL to use (defaults to IID_URL).
        :param extra_headers: additional headers to merge into the request headers.
        :return: TopicManagementResponse
        """
        url = join_url(base_url or self.IID_URL, uri)
        if extra_headers:
            headers = headers or await self.prepare_headers()
            headers.update(extra_headers)
        return await self._send_topic_request(url=url, json_payload=json_payload, headers=headers, content=content)

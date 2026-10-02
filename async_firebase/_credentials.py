"""Credential management for Firebase Cloud Messaging."""

import asyncio
import logging
import typing as t
from datetime import datetime, timedelta, timezone
from pathlib import PurePath
from urllib.parse import urlencode

import httpx
from google.oauth2 import service_account  # type: ignore


# A list of accessible OAuth 2.0 scopes can be found
# https://developers.google.com/identity/protocols/oauth2/scopes.
DEFAULT_SCOPES: t.Tuple[str, ...] = ("https://www.googleapis.com/auth/cloud-platform",)

TOKEN_URL: str = "https://oauth2.googleapis.com/token"


class CredentialManager:
    """Manages Google OAuth 2.0 credentials and access token lifecycle."""

    def __init__(
        self,
        credentials: t.Optional[service_account.Credentials] = None,
        scopes: t.Optional[t.List[str]] = None,
    ) -> None:
        self._credentials: service_account.Credentials = credentials
        self.scopes: t.List[str] = scopes or list(DEFAULT_SCOPES)
        self._token_lock: asyncio.Lock = asyncio.Lock()

    @property
    def credentials(self) -> service_account.Credentials:
        return self._credentials

    def from_service_account_info(self, service_account_info: t.Dict[str, str]) -> None:
        """
        Creates a Credentials instance from parsed service account info.

        :param service_account_info: the service account info in Google format.
        """
        self._credentials = service_account.Credentials.from_service_account_info(
            info=service_account_info, scopes=self.scopes
        )

    def from_service_account_file(self, service_account_filename: t.Union[str, PurePath]) -> None:
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

    async def get_access_token(self, http_client: httpx.AsyncClient) -> str:
        """Get a valid OAuth 2.0 access token, refreshing if necessary.

        :param http_client: the async HTTP client to use for the token refresh request.
        """
        if self._credentials.valid:
            return self._credentials.token

        async with self._token_lock:
            # Double-check after acquiring the lock, another coroutine may have refreshed already.
            if self._credentials.valid:
                return self._credentials.token

            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            data = urlencode(
                {
                    "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                    "assertion": self._credentials._make_authorization_grant_assertion(),
                }
            ).encode("utf-8")

            response: httpx.Response = await http_client.post(TOKEN_URL, content=data, headers=headers)
            response_data = response.json()

            self._credentials.expiry = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(
                seconds=response_data["expires_in"]
            )
            self._credentials.token = response_data["access_token"]
            return self._credentials.token

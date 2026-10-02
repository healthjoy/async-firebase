"""Tests for async_firebase._credentials module."""

import asyncio
from datetime import datetime, timedelta
from pathlib import PurePath
from unittest import mock

import httpx
import pytest
from google.oauth2 import service_account

from async_firebase._credentials import CredentialManager


pytestmark = pytest.mark.asyncio


def test_from_service_account_file_with_purepath(fake_service_account_file):
    """Test that PurePath is converted to string before passing to google-auth."""
    manager = CredentialManager()
    pure_path = PurePath(fake_service_account_file)
    manager.from_service_account_file(pure_path)
    assert isinstance(manager.credentials, service_account.Credentials)


def test_from_service_account_file_with_string(fake_service_account_file):
    """Test that string path works directly."""
    manager = CredentialManager()
    manager.from_service_account_file(str(fake_service_account_file))
    assert isinstance(manager.credentials, service_account.Credentials)


async def test_get_access_token_when_valid(fake_service_account):
    """When credentials are already valid, return the cached token without HTTP call."""
    manager = CredentialManager()
    manager.from_service_account_info(fake_service_account)
    manager._credentials.token = "cached-token"
    # Make the credentials appear valid by setting expiry to the future
    manager._credentials.expiry = datetime.utcnow() + timedelta(hours=1)

    mock_client = mock.AsyncMock(spec=httpx.AsyncClient)
    token = await manager.get_access_token(mock_client)

    assert token == "cached-token"
    # No HTTP call should have been made
    mock_client.post.assert_not_awaited()


async def test_get_access_token_refreshes_when_expired(fake_service_account):
    """When credentials are expired, perform the token refresh HTTP flow."""
    manager = CredentialManager()
    manager.from_service_account_info(fake_service_account)

    mock_response = mock.MagicMock(spec=httpx.Response)
    mock_response.json.return_value = {
        "access_token": "new-access-token",
        "expires_in": 3600,
    }

    mock_client = mock.AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.return_value = mock_response

    token = await manager.get_access_token(mock_client)

    assert token == "new-access-token"
    assert manager._credentials.token == "new-access-token"
    assert manager._credentials.expiry is not None
    mock_client.post.assert_awaited_once()


async def test_get_access_token_double_check_lock(fake_service_account):
    """When two coroutines race, the second should find the token already refreshed."""
    manager = CredentialManager()
    manager.from_service_account_info(fake_service_account)

    call_count = 0

    async def fake_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        # Simulate network delay
        await asyncio.sleep(0.01)
        mock_resp = mock.MagicMock(spec=httpx.Response)
        mock_resp.json.return_value = {
            "access_token": "refreshed-token",
            "expires_in": 3600,
        }
        return mock_resp

    mock_client = mock.AsyncMock(spec=httpx.AsyncClient)
    mock_client.post.side_effect = fake_post

    # Launch two concurrent token requests
    tokens = await asyncio.gather(
        manager.get_access_token(mock_client),
        manager.get_access_token(mock_client),
    )

    # Both should get the same token
    assert tokens[0] == "refreshed-token"
    assert tokens[1] == "refreshed-token"
    # Only one HTTP call should have been made (lock prevents duplicate)
    assert call_count == 1


def test_custom_scopes():
    """Test that custom scopes are passed through."""
    custom_scopes = ["https://www.googleapis.com/auth/firebase.messaging"]
    manager = CredentialManager(scopes=custom_scopes)
    assert manager.scopes == custom_scopes


def test_default_scopes():
    """Test that default scopes are used when none provided."""
    manager = CredentialManager()
    assert manager.scopes == ["https://www.googleapis.com/auth/cloud-platform"]

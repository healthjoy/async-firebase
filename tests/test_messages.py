"""Tests for async_firebase.messages module."""

from unittest import mock

import httpx
import pytest

from async_firebase.messages import (
    APNSConfig,
    TopicManagementResponse,
)


def test_apns_config_build_without_topic_and_collapse_key(freezer):
    """APNSConfig.build() should omit apns-topic and apns-collapse-id when not provided."""
    config = APNSConfig.build(
        priority="normal",
        ttl=3600,
        alert="Test alert",
        badge=1,
    )
    assert "apns-topic" not in config.headers
    assert "apns-collapse-id" not in config.headers
    assert "apns-expiration" in config.headers
    assert "apns-priority" in config.headers


def test_apns_config_build_with_topic_and_collapse_key(freezer):
    """APNSConfig.build() should include apns-topic and apns-collapse-id when provided."""
    config = APNSConfig.build(
        priority="high",
        ttl=3600,
        apns_topic="my-topic",
        collapse_key="my-key",
        alert="Test alert",
        badge=1,
    )
    assert config.headers["apns-topic"] == "my-topic"
    assert config.headers["apns-collapse-id"] == "my-key"


def test_topic_management_response_no_results():
    """TopicManagementResponse should raise ValueError when results are missing."""
    mock_response = mock.MagicMock(spec=httpx.Response)
    mock_response.json.return_value = {}

    with pytest.raises(ValueError, match="Unexpected topic management response"):
        TopicManagementResponse(resp=mock_response)

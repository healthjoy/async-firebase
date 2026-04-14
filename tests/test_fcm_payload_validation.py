"""Integration tests that validate push message payloads against the real FCM API using dry_run=True.

These tests require valid Firebase credentials. Set the environment variable
``FIREBASE_SERVICE_ACCOUNT_KEY`` to the path of a service-account JSON file.
When credentials are absent the tests are skipped automatically.

dry_run=True tells FCM to validate the entire message structure (payload format,
field types, enum values) without delivering the message. Messages are addressed
to a topic (not a device token) so FCM validates the full payload without
short-circuiting on token validation.
"""

import json
import os
from datetime import datetime

import pytest
import pytest_asyncio

from async_firebase.client import AsyncFirebaseClient
from async_firebase.errors import InvalidArgumentError
from async_firebase.messages import (
    AndroidConfig,
    AndroidNotification,
    AndroidNotificationPriority,
    APNSConfig,
    LightSettings,
    Message,
    Notification,
    NotificationProxy,
    Visibility,
)
from async_firebase.serialization import serialize_message


_service_account_path = os.environ.get("FIREBASE_SERVICE_ACCOUNT_KEY")


def _has_valid_credentials() -> bool:
    """Check that the service account file exists and contains valid JSON."""
    if not _service_account_path or not os.path.isfile(_service_account_path):
        return False
    try:
        with open(_service_account_path) as f:
            json.load(f)
    except (json.JSONDecodeError, OSError):
        return False
    return True


# Topic used for dry_run validation — no real subscribers needed.
_TEST_TOPIC = "payload-validation-test"

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.integration,
    pytest.mark.skipif(
        not _has_valid_credentials(),
        reason="FIREBASE_SERVICE_ACCOUNT_KEY not set or not valid JSON (expected in Dependabot runs)",
    ),
]


@pytest_asyncio.fixture()
async def fcm_client():
    client = AsyncFirebaseClient()
    client.creds_from_service_account_file(_service_account_path)
    async with client:
        yield client


def _assert_payload_accepted(response):
    """Assert that FCM accepted the payload structure.

    With dry_run=True and a topic target, a successful response (no exception)
    means FCM fully validated the payload. INVALID_ARGUMENT means the payload
    is malformed — the test must fail.
    """
    assert not isinstance(response.exception, InvalidArgumentError), (
        f"FCM rejected the payload as INVALID_ARGUMENT: {response.exception}"
    )


async def test_standard_android_push_payload(fcm_client):
    """Validate a fully-populated Android push payload passes FCM validation."""
    android_config = AndroidConfig.build(
        priority="high",
        ttl=3600,
        collapse_key="test-collapse",
        title="Integration Test",
        body="Payload validation via dry_run",
        tag="test-tag",
        channel_id="test-channel",
        image="https://example.com/icon.png",
        ticker="ticker text",
        sticky=False,
        event_timestamp=datetime(2026, 1, 15, 12, 0, 0),
        local_only=False,
        notification_priority=AndroidNotificationPriority.HIGH,
        vibrate_timings_millis=[100, 200, 100, 200],
        default_vibrate_timings=False,
        default_sound=True,
        light_settings=LightSettings(color="#ff0000", light_on_duration_millis=500, light_off_duration_millis=1000),
        default_light_settings=False,
        notification_count=3,
        visibility=Visibility.PRIVATE,
        proxy=NotificationProxy.ALLOW,
    )
    message = Message(android=android_config, topic=_TEST_TOPIC)
    response = await fcm_client.send(message, dry_run=True)
    _assert_payload_accepted(response)


async def test_silent_android_push_payload(fcm_client):
    """Validate a data-only (silent) Android push payload passes FCM validation."""
    android_config = AndroidConfig.build(
        priority="normal",
        ttl=600,
        data={"action": "sync", "resource_id": "42"},
    )
    message = Message(android=android_config, topic=_TEST_TOPIC)
    response = await fcm_client.send(message, dry_run=True)
    _assert_payload_accepted(response)


async def test_standard_apns_push_payload(fcm_client):
    """Validate a standard iOS (APNS) push payload passes FCM validation."""
    apns_config = APNSConfig.build(
        priority="high",
        apns_topic="com.example.app",
        collapse_key="test-collapse",
        title="Integration Test",
        alert="Payload validation via dry_run",
        badge=1,
        sound="default",
        category="TEST_CATEGORY",
        mutable_content=True,
    )
    message = Message(apns=apns_config, topic=_TEST_TOPIC)
    response = await fcm_client.send(message, dry_run=True)
    _assert_payload_accepted(response)


async def test_silent_apns_push_payload(fcm_client):
    """Validate a silent (content-available) iOS push payload passes FCM validation."""
    apns_config = APNSConfig.build(
        priority="normal",
        apns_topic="com.example.app",
        content_available=True,
        custom_data={"action": "background_refresh"},
    )
    message = Message(apns=apns_config, topic=_TEST_TOPIC)
    response = await fcm_client.send(message, dry_run=True)
    _assert_payload_accepted(response)


async def test_cross_platform_push_payload(fcm_client):
    """Validate a message with both Android and APNS configs passes FCM validation."""
    android_config = AndroidConfig.build(
        priority="high",
        ttl=3600,
        title="Cross-platform Test",
        body="Testing both platforms",
        visibility=Visibility.PUBLIC,
    )
    apns_config = APNSConfig.build(
        priority="high",
        apns_topic="com.example.app",
        title="Cross-platform Test",
        alert="Testing both platforms",
        badge=1,
        sound="default",
    )
    message = Message(
        notification=Notification(title="Cross-platform Test", body="Testing both platforms"),
        android=android_config,
        apns=apns_config,
        topic=_TEST_TOPIC,
    )
    response = await fcm_client.send(message, dry_run=True)
    _assert_payload_accepted(response)


def _build_valid_payload():
    """Build a correctly serialized payload with all fragile fields populated."""
    return serialize_message(
        Message(
            android=AndroidConfig(
                priority="high",
                notification=AndroidNotification(
                    title="Payload test",
                    body="Testing wire format",
                    visibility=Visibility.PRIVATE,
                    priority=AndroidNotificationPriority.HIGH,
                    event_timestamp=datetime(2026, 1, 15, 12, 0, 0),
                    proxy=NotificationProxy.ALLOW,
                ),
            ),
            topic=_TEST_TOPIC,
        ),
        dry_run=True,
    )


def _inject_bad_field(payload, field, value):
    """Replace a field in the android notification dict."""
    payload["message"]["android"]["notification"][field] = value
    return payload


def _rename_field(payload, old_key, new_key):
    """Rename a key in the android notification dict (simulates wrong wire-format key)."""
    notif = payload["message"]["android"]["notification"]
    notif[new_key] = notif.pop(old_key)
    return payload


@pytest.mark.parametrize(
    "description, mutate_payload",
    [
        (
            "visibility with VISIBILITY_ prefix",
            lambda p: _inject_bad_field(p, "visibility", "VISIBILITY_PRIVATE"),
        ),
        (
            "priority with wrong key name",
            lambda p: _rename_field(p, "notification_priority", "priority"),
        ),
        (
            "event_time with wrong key name",
            lambda p: _rename_field(p, "event_time", "event_timestamp"),
        ),
    ],
    ids=[
        "visibility-prefixed",
        "priority-wrong-key",
        "event_time-wrong-key",
    ],
)
async def test_fcm_rejects_malformed_wire_format(fcm_client, description, mutate_payload):
    """Verify FCM rejects known wire-format mistakes that are easy to regress on.

    Each case reproduces a specific serialization bug. The test builds a valid
    payload, injects the exact mistake, and asserts FCM returns INVALID_ARGUMENT.
    """
    malformed_payload = mutate_payload(_build_valid_payload())

    response = await fcm_client.send_fcm_request(
        uri=fcm_client.FCM_ENDPOINT.format(project_id=fcm_client._credentials.project_id),
        json_payload=malformed_payload,
    )
    assert isinstance(response.exception, InvalidArgumentError), (
        f"Expected FCM to reject '{description}' with INVALID_ARGUMENT, got: {response.exception}"
    )

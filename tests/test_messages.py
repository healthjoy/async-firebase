"""Tests for async_firebase.messages module."""

from datetime import datetime
from unittest import mock

import httpx
import pytest

from async_firebase.messages import (
    AndroidConfig,
    AndroidFCMOptions,
    AndroidNotificationPriority,
    APNSConfig,
    APNSFCMOptions,
    CriticalSound,
    LightSettings,
    NotificationProxy,
    TopicManagementResponse,
    Visibility,
    WebpushConfig,
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


def test_android_config_build_with_new_fields(freezer):
    """AndroidConfig.build() should pass through all new AndroidNotification fields."""
    config = AndroidConfig.build(
        priority="high",
        image="https://example.com/image.png",
        ticker="Ticker text",
        sticky=True,
        event_timestamp=datetime(2025, 6, 15, 12, 0, 0),
        local_only=True,
        notification_priority=AndroidNotificationPriority.MAX,
        vibrate_timings_millis=[100, 200, 300],
        default_vibrate_timings=False,
        default_sound=False,
        light_settings=LightSettings(color="#ff0000", light_on_duration_millis=500, light_off_duration_millis=1000),
        default_light_settings=False,
        notification_count=3,
        visibility=Visibility.PUBLIC,
        proxy=NotificationProxy.ALLOW,
        fcm_options=AndroidFCMOptions(analytics_label="campaign_1"),
        direct_boot_ok=True,
        bandwidth_constrained_ok=True,
        restricted_satellite_ok=False,
    )
    notif = config.notification
    assert notif.image == "https://example.com/image.png"
    assert notif.ticker == "Ticker text"
    assert notif.sticky is True
    assert notif.event_timestamp == datetime(2025, 6, 15, 12, 0, 0)
    assert notif.local_only is True
    assert notif.priority == AndroidNotificationPriority.MAX
    assert notif.vibrate_timings_millis == [100, 200, 300]
    assert notif.default_vibrate_timings is False
    assert notif.default_sound is False
    assert notif.light_settings.color == "#ff0000"
    assert notif.default_light_settings is False
    assert notif.notification_count == 3
    assert notif.visibility == Visibility.PUBLIC
    assert notif.proxy == NotificationProxy.ALLOW
    assert config.fcm_options.analytics_label == "campaign_1"
    assert config.direct_boot_ok is True
    assert config.bandwidth_constrained_ok is True
    assert config.restricted_satellite_ok is False


def test_apns_config_build_with_new_fields(freezer):
    """APNSConfig.build() should pass through subtitle, CriticalSound, fcm_options, and live_activity_token."""
    config = APNSConfig.build(
        priority="high",
        ttl=3600,
        title="Title",
        subtitle="Subtitle",
        alert="Alert body",
        badge=1,
        sound=CriticalSound(name="alarm.caf", critical=True, volume=0.8),
        fcm_options=APNSFCMOptions(analytics_label="campaign_2", image="https://example.com/img.png"),
        live_activity_token="live-token-123",
    )
    assert config.payload.aps.alert.subtitle == "Subtitle"
    assert isinstance(config.payload.aps.sound, CriticalSound)
    assert config.payload.aps.sound.name == "alarm.caf"
    assert config.fcm_options.analytics_label == "campaign_2"
    assert config.fcm_options.image == "https://example.com/img.png"
    assert config.live_activity_token == "live-token-123"


def test_webpush_config_build_vibrate_list():
    """WebpushConfig.build() should accept vibrate as a list of ints."""
    config = WebpushConfig.build(
        data={"key": "value"},
        vibrate=[200, 100, 200],
    )
    assert config.notification.vibrate == [200, 100, 200]

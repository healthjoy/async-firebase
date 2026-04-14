from datetime import datetime

import pytest

from async_firebase.messages import (
    AndroidNotification,
    AndroidNotificationPriority,
    Aps,
    ApsAlert,
    CriticalSound,
    LightSettings,
    NotificationProxy,
    Visibility,
)
from async_firebase.serialization import (
    aps_encoder,
    encode_android_notification,
    encode_critical_sound,
    encode_light_settings,
)


@pytest.mark.parametrize(
    "aps_obj, exp_result",
    (
        (
            Aps(
                alert="push text",
                badge=5,
                sound="default",
                content_available=True,
                category="NEW_MESSAGE",
                mutable_content=False,
            ),
            {
                "aps": {
                    "alert": "push text",
                    "badge": 5,
                    "sound": "default",
                    "content-available": 1,
                    "category": "NEW_MESSAGE",
                    "thread-id": None,
                    "mutable-content": 0,
                },
            },
        ),
        (
            Aps(
                alert=ApsAlert(
                    title="push-title",
                    body="push-text",
                ),
                badge=5,
                sound="default",
                content_available=True,
                category="NEW_MESSAGE",
                mutable_content=False,
            ),
            {
                "aps": {
                    "alert": {
                        "title": "push-title",
                        "subtitle": None,
                        "body": "push-text",
                        "loc-key": None,
                        "loc-args": [],
                        "title-loc-key": None,
                        "title-loc-args": [],
                        "action-loc-key": None,
                        "launch-image": None,
                    },
                    "badge": 5,
                    "sound": "default",
                    "content-available": 1,
                    "category": "NEW_MESSAGE",
                    "thread-id": None,
                    "mutable-content": 0,
                },
            },
        ),
        (
            Aps(
                alert="push text",
                badge=5,
                sound="default",
                content_available=True,
                category="NEW_MESSAGE",
                mutable_content=False,
                custom_data={
                    "str_attr": "value_1",
                    "int_attr": 42,
                    "float_attr": 42.42,
                    "list_attr": [1, 2, 3],
                    "dict_attr": {"a": "A", "b": "B"},
                    "bool_attr": False,
                },
            ),
            {
                "aps": {
                    "alert": "push text",
                    "badge": 5,
                    "sound": "default",
                    "content-available": 1,
                    "category": "NEW_MESSAGE",
                    "thread-id": None,
                    "mutable-content": 0,
                },
                "str_attr": "value_1",
                "int_attr": 42,
                "float_attr": 42.42,
                "list_attr": [1, 2, 3],
                "dict_attr": {"a": "A", "b": "B"},
                "bool_attr": False,
            },
        ),
        (None, None),
    ),
)
def test_aps_encoder(aps_obj, exp_result):
    aps_dict = aps_encoder(aps_obj)
    assert aps_dict == exp_result

def test_aps_encoder_does_not_modify_custom_data():
    custom_data = {
        "str_attr": "value_1",
        "int_attr": 42,
        "float_attr": 42.42,
        "list_attr": [1, 2, 3],
        "dict_attr": {"a": "A", "b": "B"},
        "bool_attr": False,
    }
    custom_data_before = custom_data.copy()

    aps = Aps(
        alert="push text",
        badge=5,
        sound="default",
        content_available=True,
        category="NEW_MESSAGE",
        mutable_content=False,
        custom_data=custom_data.copy(),
    )

    assert aps.custom_data == custom_data
    aps_encoder(aps)
    assert custom_data == custom_data_before
    assert aps.custom_data == custom_data


def test_aps_encoder_with_subtitle():
    aps = Aps(
        alert=ApsAlert(title="Title", subtitle="Subtitle", body="Body"),
        badge=1,
        sound="default",
        mutable_content=True,
    )
    result = aps_encoder(aps)
    assert result["aps"]["alert"]["subtitle"] == "Subtitle"


def test_aps_encoder_with_aps_alert_custom_data():
    aps = Aps(
        alert=ApsAlert(title="Title", body="Body", custom_data={"my-key": "my-value"}),
        badge=1,
        sound="default",
        mutable_content=True,
    )
    result = aps_encoder(aps)
    assert result["aps"]["alert"]["my-key"] == "my-value"


def test_aps_encoder_with_critical_sound():
    aps = Aps(
        alert="push text",
        badge=1,
        sound=CriticalSound(name="alarm.caf", critical=True, volume=0.8),
        mutable_content=True,
    )
    result = aps_encoder(aps)
    assert result["aps"]["sound"] == {"name": "alarm.caf", "critical": 1, "volume": 0.8}


def test_encode_critical_sound():
    sound = CriticalSound(name="alarm.caf", critical=True, volume=0.5)
    result = encode_critical_sound(sound)
    assert result == {"name": "alarm.caf", "critical": 1, "volume": 0.5}


def test_encode_critical_sound_not_critical():
    sound = CriticalSound(name="default", critical=False)
    result = encode_critical_sound(sound)
    assert result == {"name": "default", "critical": 0}


def test_encode_critical_sound_minimal():
    sound = CriticalSound(name="default")
    result = encode_critical_sound(sound)
    assert result == {"name": "default"}


def test_encode_light_settings_rrggbb():
    ls = LightSettings(color="#ff0000", light_on_duration_millis=500, light_off_duration_millis=1000)
    result = encode_light_settings(ls)
    assert result == {
        "color": {"red": 1.0, "green": 0.0, "blue": 0.0, "alpha": 1.0},
        "light_on_duration": "0.5s",
        "light_off_duration": "1.0s",
    }


def test_encode_light_settings_rrggbbaa():
    ls = LightSettings(color="#00ff0080", light_on_duration_millis=200, light_off_duration_millis=300)
    result = encode_light_settings(ls)
    assert result["color"]["green"] == 1.0
    assert result["color"]["alpha"] == pytest.approx(128 / 255.0)


def test_encode_android_notification_visibility():
    notif = AndroidNotification(visibility=Visibility.PUBLIC)
    result = encode_android_notification(notif)
    assert result["visibility"] == "PUBLIC"


def test_encode_android_notification_proxy():
    notif = AndroidNotification(proxy=NotificationProxy.IF_PRIORITY_LOWERED)
    result = encode_android_notification(notif)
    assert result["proxy"] == "IF_PRIORITY_LOWERED"


def test_encode_android_notification_priority():
    notif = AndroidNotification(priority=AndroidNotificationPriority.HIGH)
    result = encode_android_notification(notif)
    assert result["notification_priority"] == "PRIORITY_HIGH"


def test_encode_android_notification_light_settings():
    notif = AndroidNotification(
        light_settings=LightSettings(color="#0000ff", light_on_duration_millis=1000, light_off_duration_millis=2000)
    )
    result = encode_android_notification(notif)
    assert "light_settings" in result
    assert result["light_settings"]["color"]["blue"] == 1.0


def test_encode_android_notification_event_timestamp():
    ts = datetime(2025, 6, 15, 12, 0, 0)
    notif = AndroidNotification(event_timestamp=ts)
    result = encode_android_notification(notif)
    assert result["event_time"] == "2025-06-15T12:00:00Z"


def test_encode_android_notification_vibrate_timings():
    notif = AndroidNotification(vibrate_timings_millis=[100, 200, 300])
    result = encode_android_notification(notif)
    assert result["vibrate_timings"] == ["0.1s", "0.2s", "0.3s"]


def test_encode_android_notification_empty():
    notif = AndroidNotification()
    result = encode_android_notification(notif)
    assert result == {}

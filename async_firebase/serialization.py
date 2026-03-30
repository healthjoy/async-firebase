"""Serialization of Message dataclasses into JSON-ready dicts for the FCM REST API.

All APNS encoding, dataclass-to-dict conversion, null stripping, and
validation happen internally.
"""

import logging
import typing as t
from copy import deepcopy
from dataclasses import fields, is_dataclass, replace
from enum import Enum

from async_firebase.messages import (
    AndroidNotification,
    Aps,
    ApsAlert,
    CriticalSound,
    LightSettings,
    Message,
    PushNotification,
)


def remove_null_values(dict_value: t.Dict[str, t.Any]) -> t.Dict[str, t.Any]:
    """Remove Falsy values from the dictionary."""
    return {k: v for k, v in dict_value.items() if v is not None and v != [] and v != {}}


def cleanup_firebase_message(dataclass_obj, dict_factory: t.Callable = dict) -> dict:
    """Recursively convert dataclasses to dicts, stripping None/empty values."""
    if is_dataclass(dataclass_obj):
        result = []
        for f in fields(dataclass_obj):
            value = cleanup_firebase_message(getattr(dataclass_obj, f.name), dict_factory)
            if isinstance(value, Enum):
                value = value.value
            result.append((f.name, value))
        return remove_null_values(dict_factory(result))
    elif isinstance(dataclass_obj, (list, tuple)):
        return type(dataclass_obj)(cleanup_firebase_message(v, dict_factory) for v in dataclass_obj)  # type: ignore
    elif isinstance(dataclass_obj, dict):
        return remove_null_values({k: cleanup_firebase_message(v, dict_factory) for k, v in dataclass_obj.items()})
    return deepcopy(dataclass_obj)


def encode_light_settings(light_settings: LightSettings) -> t.Dict[str, t.Any]:
    """Encode LightSettings to FCM wire format.

    Converts hex color to RGBA float dict and durations to protobuf-style strings.
    """
    color_hex = light_settings.color.lstrip("#")
    if len(color_hex) == 6:
        color_hex += "ff"
    r = int(color_hex[0:2], 16) / 255.0
    g = int(color_hex[2:4], 16) / 255.0
    b = int(color_hex[4:6], 16) / 255.0
    a = int(color_hex[6:8], 16) / 255.0

    return {
        "color": {"red": r, "green": g, "blue": b, "alpha": a},
        "light_on_duration": f"{light_settings.light_on_duration_millis / 1000}s",
        "light_off_duration": f"{light_settings.light_off_duration_millis / 1000}s",
    }


def encode_android_notification(notification: AndroidNotification) -> t.Dict[str, t.Any]:
    """Encode AndroidNotification fields that need wire-format transformation.

    Handles enum serialization for visibility, proxy, and priority,
    as well as LightSettings and event_timestamp encoding.
    Returns a dict ready for merging into the notification payload.
    """
    result: t.Dict[str, t.Any] = {}

    if notification.visibility is not None:
        result["visibility"] = notification.visibility.upper()

    if notification.proxy is not None:
        result["proxy"] = notification.proxy.upper()

    if notification.priority is not None:
        result["notification_priority"] = f"PRIORITY_{notification.priority.upper()}"

    if notification.light_settings is not None:
        result["light_settings"] = encode_light_settings(notification.light_settings)

    if notification.event_timestamp is not None:
        result["event_time"] = notification.event_timestamp.isoformat() + "Z"

    if notification.vibrate_timings_millis is not None:
        result["vibrate_timings"] = [f"{ms / 1000}s" for ms in notification.vibrate_timings_millis]

    return result


def encode_critical_sound(sound: CriticalSound) -> t.Dict[str, t.Any]:
    """Encode CriticalSound to APNS wire format."""
    result: t.Dict[str, t.Any] = {"name": sound.name}
    if sound.critical is not None:
        result["critical"] = 1 if sound.critical else 0
    if sound.volume is not None:
        result["volume"] = sound.volume
    return result


def aps_encoder(aps: Aps) -> t.Optional[t.Dict[str, t.Any]]:
    """Encode APS instance to JSON so it can be handled by APNS.

    Encode the message according to https://firebase.google.com/docs/reference/fcm/rest/v1/projects.messages#apnsconfig
    :param aps: instance of ``messages.Aps`` class.
    :return: APNS compatible payload.
    """
    if not aps:
        return None

    custom_data: t.Dict[str, t.Any] = deepcopy(aps.custom_data) or {}  # type: ignore

    if isinstance(aps.alert, ApsAlert):
        alert_dict: t.Dict[str, t.Any] = {
            "title": aps.alert.title,
            "subtitle": aps.alert.subtitle,
            "body": aps.alert.body,
            "loc-key": aps.alert.loc_key,
            "loc-args": aps.alert.loc_args,
            "title-loc-key": aps.alert.title_loc_key,
            "title-loc-args": aps.alert.title_loc_args,
            "action-loc-key": aps.alert.action_loc_key,
            "launch-image": aps.alert.launch_image,
        }
        if aps.alert.custom_data:
            alert_dict.update(aps.alert.custom_data)
        alert_value: t.Any = alert_dict
    else:
        alert_value = aps.alert

    if isinstance(aps.sound, CriticalSound):
        sound_value: t.Any = encode_critical_sound(aps.sound)
    else:
        sound_value = aps.sound

    payload = {
        "aps": {
            "alert": alert_value,
            "badge": aps.badge,
            "sound": sound_value,
            "category": aps.category,
            "thread-id": aps.thread_id,
            "mutable-content": 1 if aps.mutable_content else 0,
        },
        **custom_data,
    }

    if aps.content_available is True:
        payload["aps"]["content-available"] = 1

    return payload


def serialize_message(message: Message, *, dry_run: bool = False) -> t.Dict[str, t.Any]:
    """Serialize a Message into a JSON-ready dict for the FCM API.

    Handles APNS payload encoding, null stripping, and validation.
    Does not mutate the input message.

    :param message: the Message to serialize.
    :param dry_run: if True, sets validate_only in the payload.
    :return: dict ready to POST to FCM.
    :raises ValueError: if the message contains no deliverable data.
    """
    # Avoid mutation of the caller's message for any transformations
    message = replace(message)

    android = message.android
    if android and android.notification:
        notification = android.notification
        android = replace(android, notification=replace(notification))
        message = replace(message, android=android)
        _android_notification_overrides = encode_android_notification(notification)
    else:
        _android_notification_overrides = None

    if message.apns and message.apns.payload:
        message = replace(message, apns=replace(message.apns))
        message.apns.payload = aps_encoder(message.apns.payload.aps)  # type: ignore

    push_notification: t.Dict[str, t.Any] = cleanup_firebase_message(
        PushNotification(message=message, validate_only=dry_run)
    )

    if _android_notification_overrides and "android" in push_notification.get("message", {}):
        android_msg = push_notification["message"]["android"]
        if "notification" in android_msg:
            notif_dict = android_msg["notification"]
            # Remove dataclass field names that differ from FCM wire-format names
            # before applying the correctly-keyed overrides.
            for stale_key in ("priority", "event_timestamp", "vibrate_timings_millis"):
                notif_dict.pop(stale_key, None)
            notif_dict.update(_android_notification_overrides)
    if len(push_notification["message"]) == 1:
        logging.warning("No data has been provided to construct push notification payload")
        raise ValueError("``messages.PushNotification`` cannot be assembled as data has not been provided")
    return push_notification

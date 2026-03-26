"""Serialization of Message dataclasses into JSON-ready dicts for the FCM REST API.

All APNS encoding, dataclass-to-dict conversion, null stripping, and
validation happen internally.
"""

import logging
import typing as t
from copy import deepcopy
from dataclasses import fields, is_dataclass, replace
from enum import Enum

from async_firebase.messages import Aps, ApsAlert, Message, PushNotification


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


def aps_encoder(aps: Aps) -> t.Optional[t.Dict[str, t.Any]]:
    """Encode APS instance to JSON so it can be handled by APNS.

    Encode the message according to https://firebase.google.com/docs/reference/fcm/rest/v1/projects.messages#apnsconfig
    :param aps: instance of ``messages.Aps`` class.
    :return: APNS compatible payload.
    """
    if not aps:
        return None

    custom_data: t.Dict[str, t.Any] = deepcopy(aps.custom_data) or {}  # type: ignore

    payload = {
        "aps": {
            "alert": (
                {
                    "title": aps.alert.title,
                    "body": aps.alert.body,
                    "loc-key": aps.alert.loc_key,
                    "loc-args": aps.alert.loc_args,
                    "title-loc-key": aps.alert.title_loc_key,
                    "title-loc-args": aps.alert.title_loc_args,
                    "action-loc-key": aps.alert.action_loc_key,
                    "launch-image": aps.alert.launch_image,
                }
                if isinstance(aps.alert, ApsAlert)
                else aps.alert
            ),
            "badge": aps.badge,
            "sound": aps.sound,
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
    if message.apns and message.apns.payload:
        # Avoid mutation of the caller's message
        message = replace(message, apns=replace(message.apns))
        message.apns.payload = aps_encoder(message.apns.payload.aps)  # type: ignore

    push_notification: t.Dict[str, t.Any] = cleanup_firebase_message(
        PushNotification(message=message, validate_only=dry_run)
    )
    if len(push_notification["message"]) == 1:
        logging.warning("No data has been provided to construct push notification payload")
        raise ValueError("``messages.PushNotification`` cannot be assembled as data has not been provided")
    return push_notification

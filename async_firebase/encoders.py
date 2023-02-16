"""The module houses encoders needed to properly form the payload.

"""
import typing as t
from copy import deepcopy

from async_firebase.messages import Aps, ApsAlert


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
            "alert": {
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
            else aps.alert,
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

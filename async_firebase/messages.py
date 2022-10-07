"""The module houses the message structures that can be used to construct a push notification payload.

"""

import typing as t
from dataclasses import dataclass, field

from async_firebase.errors import AsyncFirebaseError


@dataclass
class AndroidNotification:
    """
    Android-specific notification parameters.

    Attributes:
    title: title of the notification (optional). If specified, overrides the title set via ``messages.Notification``.
    body: body of the notification (optional). If specified, overrides the body set via ``messages.Notification``.
    icon: icon of the notification (optional).
    color: color of the notification icon expressed in ``#rrggbb`` form (optional).
    sound: sound to be played when the device receives the notification (optional). This is usually the file name of
        the sound resource.
    tag: tag of the notification (optional). This is an identifier used to replace existing notifications in the
        notification drawer. If not specified, each request creates a new notification.
    click_action: the action associated with a user click on the notification (optional). If specified, an activity with
        a matching intent filter is launched when a user clicks on the notification.
    body_loc_key: key of the body string in the app's string resources to use to localize the body text (optional).
    body_loc_args: a list of resource keys that will be used in place of the format specifiers in ``body_loc_key``
        (optional).
    title_loc_key: key of the title string in the app's string resources to use to localize the title text (optional).
    title_loc_args: a list of resource keys that will be used in place of the format specifiers in ``title_loc_key``
        (optional).
    """

    title: t.Optional[str] = None
    body: t.Optional[str] = None
    icon: t.Optional[str] = None
    color: t.Optional[str] = None
    sound: t.Optional[str] = None
    tag: t.Optional[str] = None
    click_action: t.Optional[str] = None
    body_loc_key: t.Optional[str] = None
    body_loc_args: t.List[str] = field(default_factory=list)
    title_loc_key: t.Optional[str] = None
    title_loc_args: t.List[str] = field(default_factory=list)
    channel_id: t.Optional[str] = None


@dataclass
class AndroidConfig:
    """
    Android-specific options that can be included in a message.

    Attributes:
    collapse_key: collapse key string for the message (optional). This is an identifier for a group of messages that
        can be collapsed, so that only the last message is sent when delivery can be resumed. A maximum of 4 different
        collapse keys may be active at a given time.
    priority: priority of the message (optional). Must be one of ``high`` or ``normal``.
    ttl: the time-to-live duration of the message (optional) represent as string. For example: 7200s
    restricted_package_name: the package name of the application where the registration tokens must match in order to
        receive the message (optional).
    data: a dictionary of data fields (optional). All keys and values in the dictionary must be strings.
    notification: a ``messages.AndroidNotification`` to be included in the message (optional).
    """

    collapse_key: t.Optional[str] = None
    priority: t.Optional[str] = None
    ttl: t.Optional[str] = None
    restricted_package_name: t.Optional[str] = None
    data: t.Dict[str, str] = field(default_factory=dict)
    notification: t.Optional[AndroidNotification] = field(default=None)


@dataclass
class ApsAlert:
    """
    An alert that can be included in ``message.Aps``.

    Attributes:
    title: title of the alert (optional). If specified, overrides the title set via ``messages.Notification``.
    body: body of the alert (optional). If specified, overrides the body set via ``messages.Notification``.
    loc_key: key of the body string in the app's string resources to use to localize the body text (optional).
    loc_args: a list of resource keys that will be used in place of the format specifiers in ``loc_key`` (optional).
    title_loc_key: key of the title string in the app's string resources to use to localize the title text (optional).
    title_loc_args: a list of resource keys that will be used in place of the format specifiers in ``title_loc_key``
        (optional).
    action_loc_key: key of the text in the app's string resources to use to localize the action button text (optional).
    launch_image: image for the notification action (optional).
    """

    title: t.Optional[str] = None
    body: t.Optional[str] = None
    loc_key: t.Optional[str] = None
    loc_args: t.List[str] = field(default_factory=list)
    title_loc_key: t.Optional[str] = None
    title_loc_args: t.List[str] = field(default_factory=list)
    action_loc_key: t.Optional[str] = None
    launch_image: t.Optional[str] = None


@dataclass
class Aps:
    """
    Aps dictionary to be included in an APNS payload.

    Attributes:
    alert: a string or a ``messages.ApsAlert`` instance (optional).
    badge: a number representing the badge to be displayed with the message (optional).
    sound: name of the sound file to be played with the message (optional).
    content_available: a boolean indicating whether to configure a background update notification (optional).
    category: string identifier representing the message type (optional).
    thread_id: an app-specific string identifier for grouping messages (optional).
    mutable_content: a boolean indicating whether to support mutating notifications at the client using app extensions
        (optional).
    custom_data: a dictionary of custom key-value pairs to be included in the Aps dictionary (optional). These
        attributes will be then re-assembled according to the format allowed by APNS. Below you may find details:

        In addition to the Apple-defined keys, custom keys may be added to payload to deliver small amounts of data
        to app, notification service app extension, or notification content app extension. Custom keys must
        have values with primitive types, such as dictionary, array, string, number, or Boolean. Custom keys are
        available in the ``userInfo`` dictionary of the ``UNNotificationContent`` object delivered to app.

        In a nutshell custom keys should be incorporated on the same level as ``apns`` attribute.
    """

    alert: t.Union[str, ApsAlert, None] = None
    badge: t.Optional[int] = None
    sound: t.Optional[str] = None
    content_available: t.Optional[bool] = None
    category: t.Optional[str] = None
    thread_id: t.Optional[str] = None
    mutable_content: t.Optional[bool] = None
    custom_data: t.Dict[str, str] = field(default_factory=dict)


@dataclass
class APNSPayload:
    """
    Payload of an APNS message.

    Attributes:
    aps: a ``messages.Aps`` instance to be included in the payload.
    """

    aps: t.Optional[Aps] = field(default=None)


@dataclass
class APNSConfig:
    """
    APNS-specific options that can be included in a message.

    Refer to APNS Documentation: https://developer.apple.com/library/content/documentation\
        /NetworkingInternet/Conceptual/RemoteNotificationsPG/CommunicatingwithAPNs.html for more information.

    Attributes:
    headers: a dictionary of headers (optional).
    payload: a ``messages.APNSPayload`` to be included in the message (optional).
    """

    headers: t.Dict[str, str] = field(default_factory=dict)
    payload: t.Optional[APNSPayload] = field(default=None)


@dataclass
class Notification:
    """
    A notification that can be included in a message.

    Attributes:
    title: title of the notification (optional).
    body: body of the notification (optional).
    image: image url of the notification (optional)
    """

    title: t.Optional[str] = None
    body: t.Optional[str] = None
    image: t.Optional[str] = None


@dataclass
class Message:
    """
    A common message that can be sent via Firebase.

    Contains payload information as well as recipient information. In particular, the message must contain exactly one
    of token, topic or condition fields.

    Attributes:
    data: a dictionary of data fields (optional). All keys and values in the dictionary must be strings.
    notification: an instance of ``messages.Notification`` (optional).
    android: an instance of ``messages.AndroidConfig`` (optional).
    webpush: an instance of ``messages.WebpushConfig`` (optional). NOT IMPLEMENTED YET.
    apns: an instance of ``messages.ApnsConfig`` (optional).
    token: the registration token of the device to which the message should be sent.
    topic: name of the Firebase topic to which the message should be sent (optional).
    condition: the Firebase condition to which the message should be sent (optional).
    """

    token: t.Optional[str]
    data: t.Dict[str, str] = field(default_factory=dict)
    notification: t.Optional[Notification] = field(default=None)
    android: t.Optional[AndroidConfig] = field(default=None)
    webpush: t.Dict[str, str] = field(default_factory=dict)
    apns: t.Optional[APNSConfig] = field(default=None)
    topic: t.Optional[str] = None
    condition: t.Optional[str] = None


@dataclass
class PushNotification:
    """The payload that is sent to Firebase Cloud Messaging.

    Attributes:
    message: an instance of ``messages.Message`` or ``messages.MulticastMessage``.
    validate_only: a boolean indicating whether to run the operation in dry run mode (optional).
    """

    message: Message
    validate_only: t.Optional[bool] = field(default=False)


class FcmPushResponse:
    """The response received from an individual batched request to the FCM API.

    The interface of this object is compatible with SendResponse object of
    the Google's firebase-admin-python package.
    """

    def __init__(
        self, fcm_response: t.Optional[t.Dict[str, str]] = None, exception: t.Optional[AsyncFirebaseError] = None
    ):
        """Inits FcmPushResponse object.

        :param fcm_response: a dictionary with the data that FCM returns as a payload
        :param exception: an exception that may happen when communicating with FCM
        """
        self.message_id = fcm_response.get("name") if fcm_response else None
        self.exception = exception

    @property
    def success(self) -> bool:
        """A boolean indicating if the request was successful."""
        return self.message_id is not None and not self.exception


class FcmPushMulticastResponse:
    """The response received from a batch request to the FCM API.

    The interface of this object is compatible with BatchResponse object of
    the Google's firebase-admin-python package.
    """

    def __init__(self, responses: t.List[FcmPushResponse]):
        """Inits FcmPushMulticastResponse.

        :param responses: a list of FcmPushResponse objects
        """
        self._responses = responses
        self._success_count = len([resp for resp in responses if resp.success])

    @property
    def responses(self):
        """A list of ``FcmPushResponse`` objects (possibly empty)."""
        return self._responses

    @property
    def success_count(self):
        return self._success_count

    @property
    def failure_count(self):
        return len(self.responses) - self.success_count

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
    channel_id: The notification's channel id (new in Android O). The app must create a channel with this channel ID
        before any notification with this channel ID is received. If you don't send this channel ID in the request,
        or if the channel ID provided has not yet been created by the app, FCM uses the channel ID specified in the
        app manifest.
    notification_count: the number of items this notification represents (optional). If zero or unspecified, systems
        that support badging use the default, which is to increment a number displayed on the long-press menu each time
        a new notification arrives.
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
    notification_count: t.Optional[int] = None


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
class WebpushFCMOptions:
    """
    Options for features provided by the FCM SDK for Web.

    Arguments:
    link: The link to open when the user clicks on the notification. Must be an HTTPS URL (optional).
    """

    link: str


@dataclass
class WebpushNotificationAction:
    """
    An action available to the users when the notification is presented.

    Arguments:
    action: Action string.
    title: Title string.
    icon: Icon URL for the action (optional).
    """

    action: t.Optional[str]
    title: t.Optional[str]
    icon: t.Optional[str] = None


@dataclass
class WebpushNotification:
    """
    Webpush-specific notification parameters.

    Arguments:
    title: title of the notification (optional). If specified, overrides the title set via ``messages.Notification``.
    body: body of the notification (optional). If specified, overrides the body set via ``messages.Notification``.
    icon: icon URL of the notification (optional).
    actions: a list of ``messages.WebpushNotificationAction`` instances (optional).
    badge: URL of the image used to represent the notification when there is not enough space to display the
        notification itself (optional).
    data: any arbitrary JSON data that should be associated with the notification (optional).
    direction: the direction in which to display the notification (optional). Must be either 'auto', 'ltr' or 'rtl'.
    image: the URL of an image to be displayed in the notification (optional).
    language: notification language (optional).
    renotify: a boolean indicating whether the user should be notified after a new notification replaces
        an old one (optional).
    require_interaction: a boolean indicating whether a notification should remain active until the user clicks or
        dismisses it, rather than closing automatically (optional).
    silent: ``True`` to indicate that the notification should be silent (optional).
    tag: an identifying tag on the notification (optional).
    timestamp_millis: a timestamp value in milliseconds on the notification (optional).
    vibrate: a vibration pattern for the device's vibration hardware to emit when the notification fires (optional).
        The pattern is specified as an integer array.
    custom_data: a dict of custom key-value pairs to be included in the notification (optional)
    """

    title: t.Optional[str] = None
    body: t.Optional[str] = None
    icon: t.Optional[str] = None
    actions: t.List[WebpushNotificationAction] = field(default_factory=list)
    badge: t.Optional[str] = None
    data: t.Dict[str, str] = field(default_factory=dict)
    direction: t.Optional[str] = None
    image: t.Optional[str] = None
    language: t.Optional[str] = None
    renotify: t.Optional[bool] = None
    require_interaction: t.Optional[bool] = None
    silent: t.Optional[bool] = None
    tag: t.Optional[str] = None
    timestamp_millis: t.Optional[int] = None
    vibrate: t.Optional[str] = None
    custom_data: t.Dict[str, str] = field(default_factory=dict)


@dataclass
class WebpushConfig:
    """
    Webpush-specific options that can be included in a message.

    Attributes:
    headers: a dictionary of headers (optional). Refer to
        [Webpush protocol](https://tools.ietf.org/html/rfc8030#section-5) for supported headers.
    data: A dictionary of data fields (optional). All keys and values in the dictionary must be
        strings. When specified, overrides any data fields set via ``Message.data``.
    notification: a ``messages.WebpushNotification`` to be included in the message (optional).
    fcm_options: a ``messages.WebpushFCMOptions`` instance to be included in the message (optional).
    """

    headers: t.Dict[str, str] = field(default_factory=dict)
    data: t.Dict[str, str] = field(default_factory=dict)
    notification: t.Optional[WebpushNotification] = field(default=None)
    fcm_options: t.Optional[WebpushFCMOptions] = field(default=None)


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
    webpush: an instance of ``messages.WebpushConfig`` (optional).
    apns: an instance of ``messages.ApnsConfig`` (optional).
    token: the registration token of the device to which the message should be sent.
    topic: name of the Firebase topic to which the message should be sent (optional).
    condition: the Firebase condition to which the message should be sent (optional).
    """

    token: t.Optional[str]
    data: t.Dict[str, str] = field(default_factory=dict)
    notification: t.Optional[Notification] = field(default=None)
    android: t.Optional[AndroidConfig] = field(default=None)
    webpush: t.Optional[WebpushConfig] = field(default=None)
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

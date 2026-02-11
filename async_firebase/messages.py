"""The module houses the message structures that can be used to construct a push notification payload."""

import typing as t
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum, IntEnum

import httpx

from async_firebase.errors import AsyncFirebaseError


DEFAULT_TTL = 604800  # 7 days in seconds

APNS_PRIORITY_HIGH = 10
APNS_PRIORITY_NORMAL = 5


class Visibility(IntEnum):
    """Available visibility levels.

    To get more insights please follow the reference
    https://developer.android.com/reference/android/app/Notification#visibility
    """

    PRIVATE = 0
    PUBLIC = 1
    SECRET = -1


class NotificationProxy(Enum):
    """Available proxy behaviors.

    To get more insights please follow the reference
    https://firebase.google.com/docs/reference/admin/dotnet/namespace/firebase-admin/messaging#notificationproxy
    """

    ALLOW = "allow"
    DENY = "deny"
    IF_PRIORITY_LOWERED = "if_priority_lowered"


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
    visibility: sets the different visibility levels of a notification. More about Visibility levels can be found by
        reference https://firebase.google.com/docs/reference/fcm/rest/v1/projects.messages#Visibility
    proxy: gets or sets the proxy behavior of this notification. Must be one of ``allow``, ``deny``, or
        ``if_priority_lowered``. If unspecified, it remains undefined and defers to the FCM backend's default mapping.
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
    visibility: t.Optional[Visibility] = None
    proxy: t.Optional[NotificationProxy] = None


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

    @classmethod
    def build(
        cls,
        *,
        priority: str,
        ttl: t.Union[int, timedelta] = DEFAULT_TTL,
        collapse_key: t.Optional[str] = None,
        restricted_package_name: t.Optional[str] = None,
        data: t.Optional[t.Dict[str, t.Any]] = None,
        title: t.Optional[str] = None,
        body: t.Optional[str] = None,
        icon: t.Optional[str] = None,
        color: t.Optional[str] = None,
        sound: t.Optional[str] = None,
        tag: t.Optional[str] = None,
        click_action: t.Optional[str] = None,
        body_loc_key: t.Optional[str] = None,
        body_loc_args: t.Optional[t.List[str]] = None,
        title_loc_key: t.Optional[str] = None,
        title_loc_args: t.Optional[t.List[str]] = None,
        channel_id: t.Optional[str] = None,
        notification_count: t.Optional[int] = None,
        visibility: "Visibility" = Visibility.PRIVATE,
        proxy: t.Optional["NotificationProxy"] = None,
    ) -> "AndroidConfig":
        """
        Constructs AndroidConfig that will be used to customize the messages that are sent to Android device.

        :param priority: sets the priority of the message. Valid values are "normal" and "high."
        :param ttl: this parameter specifies how long (in seconds) the message should be kept in Firebase storage if the
            device is offline. The maximum time to live supported is 4 weeks, and the default value is 4 weeks.
        :param collapse_key: this parameter identifies a group of messages that can be collapsed, so that only the last
            message gets sent when delivery can be resumed.
        :param restricted_package_name: The package name of the application where the registration tokens must match in
            order to receive the message (optional).
        :param data: A dictionary of data fields (optional). All keys and values in the dictionary must be strings.
        :param title: Title of the notification (optional).
        :param body: Body of the notification (optional).
        :param icon: Icon of the notification (optional).
        :param color: Color of the notification icon expressed in ``#rrggbb`` form (optional).
        :param sound: Sound to be played when the device receives the notification (optional). This is usually the file
            name of the sound resource.
        :param tag: Tag of the notification (optional). This is an identifier used to replace existing notifications in
            the notification drawer. If not specified, each request creates a new notification.
        :param click_action: The action associated with a user click on the notification (optional). If specified, an
            activity with a matching intent filter is launched when a user clicks on the notification.
        :param body_loc_key: Key of the body string in the app's string resources to use to localize the
            body text (optional).
        :param body_loc_args: A list of resource keys that will be used in place of the format specifiers
            in ``body_loc_key`` (optional).
        :param title_loc_key: Key of the title string in the app's string resources to use to localize the
            title text (optional).
        :param title_loc_args: A list of resource keys that will be used in place of the format specifiers
            in ``title_loc_key`` (optional).
        :param channel_id: Notification channel id, used by android to allow user to configure notification display
            rules on per-channel basis (optional).
        :param notification_count: The number of items in notification. May be displayed as a badge count for launchers
            that support badging. If zero or unspecified, systems that support badging use the default, which is to
            increment a number displayed on the long-press menu each time a new notification arrives (optional).
        :param visibility: set the visibility of the notification. The default level, VISIBILITY_PRIVATE.
        :param proxy: set the proxy behaviour. The default behaviour is set to None.
        :return: an instance of ``messages.AndroidConfig`` to be included in the resulting payload.
        """
        return cls(
            collapse_key=collapse_key,
            priority=priority,
            ttl=f"{int(ttl.total_seconds()) if isinstance(ttl, timedelta) else ttl}s",
            restricted_package_name=restricted_package_name,
            data={str(key): "null" if value is None else str(value) for key, value in data.items()} if data else {},
            notification=AndroidNotification(
                title=title,
                body=body,
                icon=icon,
                color=color,
                sound=sound,
                tag=tag,
                click_action=click_action,
                body_loc_key=body_loc_key,
                body_loc_args=body_loc_args or [],
                title_loc_key=title_loc_key,
                title_loc_args=title_loc_args or [],
                channel_id=channel_id,
                notification_count=notification_count,
                visibility=visibility,
                proxy=proxy,
            ),
        )


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

    @classmethod
    def build(
        cls,
        *,
        priority: str,
        ttl: int = DEFAULT_TTL,
        apns_topic: t.Optional[str] = None,
        collapse_key: t.Optional[str] = None,
        title: t.Optional[str] = None,
        alert: t.Optional[str] = None,
        badge: t.Optional[int] = None,
        sound: t.Optional[str] = None,
        content_available: bool = False,
        category: t.Optional[str] = None,
        thread_id: t.Optional[str] = None,
        mutable_content: bool = True,
        custom_data: t.Optional[t.Dict[str, t.Any]] = None,
        loc_key: t.Optional[str] = None,
        loc_args: t.Optional[t.List[str]] = None,
        title_loc_key: t.Optional[str] = None,
        title_loc_args: t.Optional[t.List[str]] = None,
        action_loc_key: t.Optional[str] = None,
        launch_image: t.Optional[str] = None,
    ) -> "APNSConfig":
        """
        Constructs APNSConfig that will be used to customize the messages that are sent to iOS device.

        :param priority: sets the priority of the message. On iOS, these correspond to APNs priorities 5 and 10.
        :param ttl: this parameter specifies how long (in seconds) the message should be kept in Firebase storage if the
            device is offline. The maximum time to live supported is 4 weeks, and the default value is 4 weeks.
        :param apns_topic: the topic for the notification. In general, the topic is your app's bundle ID/app ID.
            It can have a suffix based on the type of push notification.
        :param collapse_key: this parameter identifies a group of messages that can be collapsed, so that only the last
            message gets sent when delivery can be resumed.
        :param title: title of the alert (optional). If specified, overrides the title set via ``messages.Notification``
        :param alert: a string or a ``messages.ApsAlert`` instance (optional).
        :param badge: the value of the badge on the home screen app icon. If not specified, the badge is not changed.
            If set to 0, the badge is removed.
        :param sound: name of the sound file to be played with the message (optional).
        :param content_available: A boolean indicating whether to configure a background update notification (optional).
        :param category: string identifier representing the message type (optional).
        :param thread_id: an app-specific string identifier for grouping messages (optional).
        :param mutable_content: A boolean indicating whether to support mutating notifications at the client using app
            extensions (optional).
        :param custom_data: A dict of custom key-value pairs to be included in the Aps dictionary (optional).
        :param loc_key: key of the body string in the app's string resources to use to localize the body text
            (optional).
        :param loc_args: a list of resource keys that will be used in place of the format specifiers in ``loc_key``
            (optional).
        :param title_loc_key: key of the title string in the app's string resources to use to localize the title text
            (optional).
        :param title_loc_args: a list of resource keys that will be used in place of the format specifiers in
            ``title_loc_key`` (optional).
        :param action_loc_key: key of the text in the app's string resources to use to localize the action button text
            (optional).
        :param launch_image: image for the notification action (optional).
        :return: an instance of ``messages.APNSConfig`` to included in the resulting payload.
        """
        apns_headers = {
            "apns-expiration": str(int(datetime.now(timezone.utc).timestamp()) + ttl),
            "apns-priority": str(APNS_PRIORITY_HIGH if priority == "high" else APNS_PRIORITY_NORMAL),
        }
        if apns_topic:
            apns_headers["apns-topic"] = apns_topic
        if collapse_key:
            apns_headers["apns-collapse-id"] = str(collapse_key)

        return cls(
            headers=apns_headers,
            payload=APNSPayload(
                aps=Aps(
                    alert=ApsAlert(
                        title=title,
                        body=alert,
                        loc_key=loc_key,
                        loc_args=loc_args or [],
                        title_loc_key=title_loc_key,
                        title_loc_args=title_loc_args or [],
                        action_loc_key=action_loc_key,
                        launch_image=launch_image,
                    ),
                    badge=badge,
                    sound="default" if alert and sound is None else sound,
                    category=category,
                    thread_id=thread_id,
                    mutable_content=mutable_content,
                    custom_data=custom_data or {},
                    content_available=True if content_available else None,
                ),
            ),
        )


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

    @classmethod
    def build(
        cls,
        *,
        data: t.Dict[str, str],
        headers: t.Optional[t.Dict[str, str]] = None,
        title: t.Optional[str] = None,
        body: t.Optional[str] = None,
        icon: t.Optional[str] = None,
        actions: t.Optional[t.List[WebpushNotificationAction]] = None,
        badge: t.Optional[str] = None,
        direction: t.Optional[str] = "auto",
        image: t.Optional[str] = None,
        language: t.Optional[str] = None,
        renotify: t.Optional[bool] = False,
        require_interaction: t.Optional[bool] = None,
        silent: t.Optional[bool] = False,
        tag: t.Optional[str] = None,
        timestamp_millis: t.Optional[int] = None,
        vibrate: t.Optional[str] = None,
        custom_data: t.Optional[t.Dict[str, str]] = None,
        link: t.Optional[str] = None,
    ) -> "WebpushConfig":
        """
        Constructs WebpushConfig that will be used to customize the messages that are sent user agents.

        :param data: A dictionary of data fields (optional). All keys and values in the dictionary must be strings.
        :param headers: a dictionary of headers (optional).
        :param title: title of the notification (optional).
        :param body: body of the notification (optional).
        :param icon: icon URL of the notification (optional).
        :param actions: a list of ``messages.WebpushNotificationAction`` instances (optional).
        :param badge: URL of the image used to represent the notification when there is not enough space to display the
            notification itself (optional).
        :param direction: the direction in which to display the notification (optional). Must be either 'auto', 'ltr'
            or 'rtl'.
        :param image: the URL of an image to be displayed in the notification (optional).
        :param language: notification language (optional).
        :param renotify: a boolean indicating whether the user should be notified after a new notification replaces
            an old one (optional).
        :param require_interaction: a boolean indicating whether a notification should remain active until the user
            clicks or dismisses it, rather than closing automatically (optional).
        :param silent: ``True`` to indicate that the notification should be silent (optional).
        :param tag: an identifying tag on the notification (optional).
        :param timestamp_millis: a timestamp value in milliseconds on the notification (optional).
        :param vibrate: a vibration pattern for the device's vibration hardware to emit when the notification
            fires (optional). The pattern is specified as an integer array.
        :param custom_data: a dict of custom key-value pairs to be included in the notification (optional)
        :param link: The link to open when the user clicks on the notification. Must be an HTTPS URL (optional).
        :return: an instance of ``messages.WebpushConfig`` to included in the resulting payload.
        """
        return cls(
            data=data,
            headers=headers or {},
            notification=WebpushNotification(
                title=title,
                body=body,
                icon=icon,
                actions=actions or [],
                badge=badge,
                direction=direction,
                image=image,
                language=language,
                renotify=renotify,
                require_interaction=require_interaction,
                silent=silent,
                tag=tag,
                timestamp_millis=timestamp_millis,
                vibrate=vibrate,
                custom_data=custom_data or {},
            ),
            fcm_options=WebpushFCMOptions(link=link) if link else None,
        )


@dataclass
class FcmOptions:
    """
    Platform independent options for features provided by the FCM SDKs
    Arguments:
        analytics_label: Label associated with the message's analytics data.
    """

    analytics_label: str


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
    fcm_options: platform independent options for features provided by the FCM SDKs.
    """

    token: t.Optional[str] = None
    data: t.Dict[str, str] = field(default_factory=dict)
    notification: t.Optional[Notification] = field(default=None)
    android: t.Optional[AndroidConfig] = field(default=None)
    webpush: t.Optional[WebpushConfig] = field(default=None)
    apns: t.Optional[APNSConfig] = field(default=None)
    topic: t.Optional[str] = None
    condition: t.Optional[str] = None
    fcm_options: t.Optional[FcmOptions] = field(default=None)


@dataclass
class MulticastMessage:
    """
    A message that can be sent to multiple tokens via Firebase.

    Attributes:
    tokens: a list of registration tokens of targeted devices.
    data: a dictionary of data fields (optional). All keys and values in the dictionary must be strings.
    notification: an instance of ``messages.Notification`` (optional).
    android: an instance of ``messages.AndroidConfig`` (optional).
    webpush: an instance of ``messages.WebpushConfig`` (optional).
    apns: an instance of ``messages.ApnsConfig`` (optional).
    fcm_options: platform independent options for features provided by the FCM SDKs.
    """

    tokens: t.List[str]
    data: t.Dict[str, str] = field(default_factory=dict)
    notification: t.Optional[Notification] = field(default=None)
    android: t.Optional[AndroidConfig] = field(default=None)
    webpush: t.Optional[WebpushConfig] = field(default=None)
    apns: t.Optional[APNSConfig] = field(default=None)
    fcm_options: t.Optional[FcmOptions] = field(default=None)

    def to_messages(self) -> t.List["Message"]:
        """Expand this multicast message into a list of individual Message objects, one per token."""
        return [
            Message(
                token=token,
                data=self.data,
                notification=self.notification,
                android=self.android,
                webpush=self.webpush,
                apns=self.apns,
                fcm_options=self.fcm_options,
            )
            for token in self.tokens
        ]


@dataclass
class PushNotification:
    """The payload that is sent to Firebase Cloud Messaging.

    Attributes:
    message: an instance of ``messages.Message`` or ``messages.MulticastMessage``.
    validate_only: a boolean indicating whether to run the operation in dry run mode (optional).
    """

    message: Message
    validate_only: t.Optional[bool] = field(default=False)


@dataclass
class FCMResponse:
    """The response received from an individual batched request to the FCM API.

    The interface of this object is compatible with SendResponse object of
    the Google's firebase-admin-python package.
    """

    fcm_response: t.Optional[t.Dict[str, str]] = field(default=None, repr=False)
    exception: t.Optional[AsyncFirebaseError] = None
    message_id: t.Optional[str] = field(default=None, init=False)

    def __post_init__(self):
        self.message_id = self.fcm_response.get("name") if self.fcm_response else None

    @property
    def success(self) -> bool:
        """A boolean indicating if the request was successful."""
        return self.message_id is not None and not self.exception


@dataclass
class FCMBatchResponse:
    """The response received from a batch request to the FCM API.

    The interface of this object is compatible with BatchResponse object of
    the Google's firebase-admin-python package.
    """

    responses: t.List[FCMResponse]
    success_count: int = field(default=0, init=False)

    def __post_init__(self):
        self.success_count = sum(1 for resp in self.responses if resp.success)

    @property
    def failure_count(self):
        return len(self.responses) - self.success_count


@dataclass
class TopicManagementErrorInfo:
    """An error encountered when performing a topic management operation."""

    index: int
    reason: str


@dataclass
class TopicManagementResponse:
    """The response received from a topic management operation."""

    resp: t.Optional[httpx.Response] = field(default=None, repr=False)
    exception: t.Optional[AsyncFirebaseError] = None
    success_count: int = field(default=0, init=False)  # tokens successfully subscribed/unsubscribed
    failure_count: int = field(default=0, init=False)  # tokens that failed due to errors
    errors: t.List[TopicManagementErrorInfo] = field(default_factory=list, init=False)  # per-token error details

    def __post_init__(self):
        if self.resp:
            self._handle_response(self.resp)

    def _handle_response(self, resp: httpx.Response):
        response = resp.json()
        results = response.get("results")
        if not results:
            raise ValueError(f"Unexpected topic management response: {resp}.")

        for index, result in enumerate(results):
            if "error" in result:
                self.failure_count += 1
                self.errors.append(TopicManagementErrorInfo(index, result["error"]))
            else:
                self.success_count += 1

"""
The module houses client to communicate with FCM - Firebase Cloud Messaging (Android, iOS and Web).

Documentation for google-auth package https://google-auth.readthedocs.io/en/latest/user-guide.html that is used
to authorize request which is being made to Firebase.
"""
import json
import logging
import typing as t
from dataclasses import replace
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.nonmultipart import MIMENonMultipart
from urllib.parse import urljoin

import httpx

from async_firebase.base import AsyncClientBase, RequestLimits, RequestTimeout  # noqa: F401
from async_firebase.encoders import aps_encoder
from async_firebase.messages import (
    AndroidConfig,
    AndroidNotification,
    APNSConfig,
    APNSPayload,
    Aps,
    ApsAlert,
    FCMBatchResponse,
    FCMResponse,
    Message,
    MulticastMessage,
    PushNotification,
    WebpushConfig,
    WebpushFCMOptions,
    WebpushNotification,
    WebpushNotificationAction,
)
from async_firebase.utils import (
    FCMBatchResponseHandler,
    FCMResponseHandler,
    cleanup_firebase_message,
    serialize_mime_message,
)


DEFAULT_TTL = 604800
BATCH_MAX_MESSAGES = MULTICAST_MESSAGE_MAX_DEVICE_TOKENS = 500


class AsyncFirebaseClient(AsyncClientBase):
    """Async wrapper for Firebase Cloud Messaging.

    The AsyncFirebaseClient relies on Service Account to enable us making a request. To get more about Service Account
    please refer to https://firebase.google.com/support/guides/service-accounts
    """

    @staticmethod
    def assemble_push_notification(
        *,
        apns_config: t.Optional[APNSConfig],
        message: Message,
        dry_run: bool,
    ) -> t.Dict[str, t.Any]:
        """
        Assemble ``messages.PushNotification`` object properly.

        :param apns_config: instance of ``messages.APNSConfig``
        :param dry_run: A boolean indicating whether to run the operation in dry run mode
        :param message: an instance of ``messages.Message``
        :return: dictionary with push notification data ready to send
        """
        has_apns_config = True if apns_config and apns_config.payload else False
        if has_apns_config:
            # avoid mutation of active message
            message.apns = replace(message.apns)  # type: ignore
            message.apns.payload = aps_encoder(apns_config.payload.aps)  # type: ignore

        push_notification: t.Dict[str, t.Any] = cleanup_firebase_message(
            PushNotification(message=message, validate_only=dry_run)
        )
        if len(push_notification["message"]) == 1:
            logging.warning("No data has been provided to construct push notification payload")
            raise ValueError("``messages.PushNotification`` cannot be assembled as data has not been provided")
        return push_notification

    @staticmethod
    def build_android_config(  # pylint: disable=too-many-locals
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
    ) -> AndroidConfig:
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
        :return: an instance of ``messages.AndroidConfig`` to be included in the resulting payload.
        """
        android_config = AndroidConfig(
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
            ),
        )

        return android_config

    @staticmethod
    def build_apns_config(  # pylint: disable=too-many-locals
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
    ) -> APNSConfig:
        """
        Constructs APNSConfig that will be used to customize the messages that are sent to iOS device.

        :param priority: sets the priority of the message. On iOS, these correspond to APNs priorities 5 and 10.
        :param ttl: this parameter specifies how long (in seconds) the message should be kept in Firebase storage if the
            device is offline. The maximum time to live supported is 4 weeks, and the default value is 4 weeks.
        :param apns_topic: the topic for the notification. In general, the topic is your app’s bundle ID/app ID.
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
            "apns-expiration": str(int(datetime.utcnow().timestamp()) + ttl),
            "apns-priority": str(10 if priority == "high" else 5),
        }
        if apns_topic:
            apns_headers["apns-topic"] = apns_topic
        if collapse_key:
            apns_headers["apns-collapse-id"] = str(collapse_key)

        apns_config = APNSConfig(
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

        return apns_config

    @staticmethod
    def build_webpush_config(  # pylint: disable=too-many-locals
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
    ) -> WebpushConfig:
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
        :param data: any arbitrary JSON data that should be associated with the notification (optional).
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
        return WebpushConfig(
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

    async def send(self, message: Message, *, dry_run: bool = False) -> FCMResponse:
        """
        Send push notification.

        :param message: the message that has to be sent.
        :param dry_run: indicating whether to run the operation in dry run mode (optional). Flag for testing the request
            without actually delivering the message. Default to ``False``.

        :raises:

            ValueError if ``messages.PushNotification`` payload cannot be assembled

        :return: instance of ``messages.FCMResponse``

            Example of raw response:

                success::

                    {
                        'name': 'projects/mobile-app/messages/0:1612788010922733%7606eb247606eb24'
                    }

                failure::

                    {
                        'error': {
                            'code': 400,
                            'details': [
                                {
                                    '@type': 'type.googleapis.com/google.rpc.BadRequest',
                                    'fieldViolations': [
                                        {
                                            'description': 'Value type for APS key [badge] is a number.',
                                            'field': 'message.apns.payload.aps.badge'
                                        }
                                    ]
                                },
                                {
                                    '@type': 'type.googleapis.com/google.firebase.fcm.v1.FcmError',
                                    'errorCode': 'INVALID_ARGUMENT'
                                }
                            ],
                            'message': 'Value type for APS key [badge] is a number.',
                            'status': 'INVALID_ARGUMENT'
                        }
                    }
        """
        push_notification = self.assemble_push_notification(apns_config=message.apns, dry_run=dry_run, message=message)

        response = await self.send_request(
            uri=self.FCM_ENDPOINT.format(project_id=self._credentials.project_id),  # type: ignore
            json_payload=push_notification,
            response_handler=FCMResponseHandler(),
        )
        if not isinstance(response, FCMResponse):
            raise ValueError("Wrong return type, perhaps because of a response handler misuse.")
        return response

    async def send_multicast(
        self,
        multicast_message: MulticastMessage,
        *,
        dry_run: bool = False,
    ) -> FCMBatchResponse:
        """
        Send Multicast push notification.

        :param multicast_message: multicast message to send targeted notifications to a set of instances of app.
            May contain up to 500 device tokens.
        :param dry_run: indicating whether to run the operation in dry run mode (optional). Flag for testing the request
            without actually delivering the message. Default to ``False``.

        :raises:

            ValueError if ``messages.PushNotification`` payload cannot be assembled
            ValueError if ``messages.MulticastMessage`` contains more than MULTICAST_MESSAGE_MAX_DEVICE_TOKENS

        :return: instance of ``messages.FCMBatchResponse``
        """

        if len(multicast_message.tokens) > MULTICAST_MESSAGE_MAX_DEVICE_TOKENS:
            raise ValueError(
                f"A single ``messages.MulticastMessage`` may contain up to {MULTICAST_MESSAGE_MAX_DEVICE_TOKENS} "
                "device tokens."
            )

        messages = [
            Message(
                token=token,
                data=multicast_message.data,
                notification=multicast_message.notification,
                android=multicast_message.android,
                webpush=multicast_message.webpush,
                apns=multicast_message.apns,
            )
            for token in multicast_message.tokens
        ]

        return await self.send_all(messages, dry_run=dry_run)

    async def send_all(
        self,
        messages: t.Union[t.List[Message], t.Tuple[Message]],
        *,
        dry_run: bool = False,
    ) -> FCMBatchResponse:
        """
        Send the given messages to FCM in a single batch.

        :param messages: the list of messages to send.
        :param dry_run: indicating whether to run the operation in dry run mode (optional). Flag for testing the request
            without actually delivering the message. Default to ``False``.
        :returns: instance of ``messages.FCMBatchResponse``
        """

        if len(messages) > BATCH_MAX_MESSAGES:
            raise ValueError(f"A list of messages must not contain more than {BATCH_MAX_MESSAGES} elements")

        multipart_message = MIMEMultipart("mixed")
        # Message should not write out it's own headers.
        setattr(multipart_message, "_write_headers", lambda self: None)

        for message in messages:
            msg = MIMENonMultipart("application", "http")
            msg["Content-Transfer-Encoding"] = "binary"
            msg["Content-ID"] = self.get_request_id()
            push_notification = self.assemble_push_notification(
                apns_config=message.apns,
                dry_run=dry_run,
                message=message,
            )
            body = self.serialize_batch_request(
                httpx.Request(
                    method="POST",
                    url=urljoin(
                        self.BASE_URL, self.FCM_ENDPOINT.format(project_id=self._credentials.project_id)  # type: ignore
                    ),
                    headers=await self.prepare_headers(),
                    content=json.dumps(push_notification),
                )
            )
            msg.set_payload(body)
            multipart_message.attach(msg)

        # encode the body: note that we can't use `as_string`, because it plays games with `From ` lines.
        body = serialize_mime_message(multipart_message, mangle_from=False)

        batch_response = await self.send_request(
            uri=self.FCM_BATCH_ENDPOINT,
            content=body,
            headers={"Content-Type": f"multipart/mixed; boundary={multipart_message.get_boundary()}"},
            response_handler=FCMBatchResponseHandler(),
        )
        if not isinstance(batch_response, FCMBatchResponse):
            raise ValueError("Wrong return type, perhaps because of a response handler misuse.")
        return batch_response

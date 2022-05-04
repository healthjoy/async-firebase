"""
The module houses client to communicate with FCM - Firebase Cloud Messaging (Android, iOS and Web).

Documentation for google-auth package https://google-auth.readthedocs.io/en/latest/user-guide.html that is used
to authorize request which is being made to Firebase.
"""
import json
import logging
import typing as t
import uuid
from dataclasses import replace
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.nonmultipart import MIMENonMultipart
from pathlib import PurePath
from urllib.parse import urlencode, urljoin

import httpx
from google.oauth2 import service_account  # type: ignore

import pkg_resources  # type: ignore
from async_firebase.encoders import aps_encoder
from async_firebase.messages import (
    AndroidConfig,
    AndroidNotification,
    APNSConfig,
    APNSPayload,
    Aps,
    ApsAlert,
    FcmPushMulticastResponse,
    FcmPushResponse,
    Message,
    Notification,
    PushNotification,
)
from async_firebase.utils import (
    FcmPushMulticastResponseHandler,
    FcmPushResponseHandler,
    cleanup_firebase_message,
    serialize_mime_message,
)

DEFAULT_TTL = 604800
MULTICAST_MESSAGE_MAX_DEVICE_TOKENS = 500


class AsyncFirebaseClient:
    """Async wrapper for Firebase Cloud Messaging.

    The AsyncFirebaseClient relies on Service Account to enable us making a request. To get more about Service Account
    please refer to https://firebase.google.com/support/guides/service-accounts
    """

    BASE_URL: str = "https://fcm.googleapis.com"
    TOKEN_URL: str = "https://oauth2.googleapis.com/token"
    FCM_ENDPOINT: str = "/v1/projects/{project_id}/messages:send"
    FCM_BATCH_ENDPOINT: str = "/batch"
    # A list of accessible OAuth 2.0 scopes can be found https://developers.google.com/identity/protocols/oauth2/scopes.
    SCOPES: t.List[str] = [
        "https://www.googleapis.com/auth/cloud-platform",
    ]

    def __init__(
        self,
        credentials: service_account.Credentials = None,
        scopes: t.List[str] = None,
    ) -> None:
        """
        :param credentials: instance of ``google.oauth2.service_account.Credentials``.
            Usually, you'll create these credentials with one of the helper constructors. To create credentials using a
            Google service account private key JSON file::

                self.creds_from_service_account_file('service-account.json')

            Or if you already have the service account file loaded::

                service_account_info = json.load(open('service_account.json'))
                self.creds_from_service_account_info(service_account_info)

        :param scopes: user-defined scopes to request during the authorization grant.
        """
        self._credentials: service_account.Credentials = credentials
        self.scopes: t.List[str] = scopes or self.SCOPES

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
            message.apns = replace(message.apns)
            message.apns.payload = aps_encoder(apns_config.payload.aps)  # type: ignore

        push_notification: t.Dict[str, t.Any] = cleanup_firebase_message(
            PushNotification(message=message, validate_only=dry_run)
        )
        if len(push_notification["message"]) == 1:
            logging.warning("No data has been provided to construct push notification payload")
            raise ValueError("``messages.PushNotification`` cannot be assembled as data has not been provided")
        return push_notification

    def creds_from_service_account_info(self, service_account_info: t.Dict[str, str]) -> None:
        """
        Creates a Credentials instance from parsed service account info.

        :param service_account_info: the service account info in Google format.
        """
        self._credentials = service_account.Credentials.from_service_account_info(
            info=service_account_info, scopes=self.scopes
        )

    def creds_from_service_account_file(self, service_account_filename: t.Union[str, PurePath]) -> None:
        """
        Creates a Credentials instance from a service account json file.

        :param service_account_filename: the path to the service account json file.
        """
        if isinstance(service_account_filename, PurePath):
            service_account_filename = str(service_account_filename)

        logging.debug("Creating credentials from file: %s", service_account_filename)
        self._credentials = service_account.Credentials.from_service_account_file(
            filename=service_account_filename, scopes=self.scopes
        )

    async def _get_access_token(self) -> str:
        """Get OAuth 2 access token."""
        if self._credentials.valid:
            return self._credentials.token

        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = urlencode(
            {
                "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
                "assertion": self._credentials._make_authorization_grant_assertion(),
            }
        ).encode("utf-8")

        async with httpx.AsyncClient() as client:
            response: httpx.Response = await client.post(self.TOKEN_URL, data=data, headers=headers)
            response_data = response.json()

        self._credentials.expiry = datetime.utcnow() + timedelta(seconds=response_data["expires_in"])
        self._credentials.token = response_data["access_token"]
        return self._credentials.token

    @staticmethod
    def build_android_config(  # pylint: disable=too-many-locals
        *,
        priority: str,
        ttl: t.Union[int, timedelta] = DEFAULT_TTL,
        collapse_key: t.Optional[str] = None,
        restricted_package_name: str = None,
        data: t.Dict[str, t.Any] = None,
        title: str = None,
        body: str = None,
        icon: str = None,
        color: str = None,
        sound: str = None,
        tag: str = None,
        click_action: str = None,
        body_loc_key: str = None,
        body_loc_args: t.List[str] = None,
        title_loc_key: str = None,
        title_loc_args: t.List[str] = None,
        channel_id: t.Optional[str] = None,
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
        :return: an instance of ``messages.AndroidConfig`` to be included in the resulting payload.
        """
        android_config = AndroidConfig(
            collapse_key=collapse_key,
            priority=priority,
            ttl=f"{int(ttl.total_seconds()) if isinstance(ttl, timedelta) else ttl}s",
            restricted_package_name=restricted_package_name,
            data={str(key): str(value) for key, value in data.items()} if data else {},
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
            ),
        )

        return android_config

    @staticmethod
    def build_apns_config(  # pylint: disable=too-many-locals
        *,
        priority: str,
        ttl: int = DEFAULT_TTL,
        apns_topic: str = None,
        collapse_key: str = None,
        title: str = None,
        alert: str = None,
        badge: int = None,
        sound: str = None,
        content_available: bool = False,
        category: str = None,
        thread_id: str = None,
        mutable_content: bool = True,
        custom_data: t.Dict[str, t.Any] = None,
        loc_key: str = None,
        loc_args: t.List[str] = None,
        title_loc_key: str = None,
        title_loc_args: t.List[str] = None,
        action_loc_key: str = None,
        launch_image: str = None,
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
    def _get_request_id():
        """Generate unique request ID."""
        return str(uuid.uuid4())

    @staticmethod
    def _serialize_batch_request(request: httpx.Request) -> str:
        """
        Convert an HttpRequest object into a string.

        :param request: `httpx.Request`, the request to serialize.
        :return: a string in application/http format.
        """
        status_line = f"{request.method} {request.url.path} HTTP/1.1\n"
        major, minor = request.headers.get("content-type", "application/json").split("/")
        msg = MIMENonMultipart(major, minor)
        headers = request.headers.copy()

        # MIMENonMultipart adds its own Content-Type header.
        if "content-type" in headers:
            del headers["content-type"]

        for key, value in headers.items():
            msg[key] = value
        msg.set_unixfrom(None)  # type: ignore

        if request.content is not None:
            msg.set_payload(request.content)
            msg["content-length"] = str(len(request.content))

        body = serialize_mime_message(msg, max_header_len=0)
        return f"{status_line}{body}"

    async def _prepare_headers(self):
        """Prepare HTTP headers that will be used to request Firebase Cloud Messaging."""
        logging.debug("Preparing HTTP headers for all the subsequent requests")
        access_token: str = await self._get_access_token()
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; UTF-8",
            "X-Request-Id": self._get_request_id(),
            "X-GOOG-API-FORMAT-VERSION": "2",
            "X-FIREBASE-CLIENT": "async-firebase/{0}".format(pkg_resources.get_distribution("async-firebase").version),
        }

    async def push(  # pylint: disable=too-many-locals
        self,
        device_token: str,
        *,
        android: t.Optional[AndroidConfig] = None,
        apns: t.Optional[APNSConfig] = None,
        condition: t.Optional[str] = None,
        data: t.Optional[t.Dict[str, str]] = None,
        notification: t.Optional[Notification] = None,
        topic: t.Optional[str] = None,
        webpush: t.Optional[t.Dict[str, str]] = None,
        dry_run: bool = False,
    ) -> FcmPushResponse:
        """
        Send push notification.

        :param device_token: device token allows to send targeted notifications to a particular instance of app.
        :param android: as instance of ``messages.AndroidConfig`` that contains Android-specific options.
        :param apns: as instance of ``messages.APNSConfig`` that contains iOS-specific options.
        :param condition: the Firebase condition to which the message should be sent.
        :param data: a dictionary of data fields. All keys and values in the dictionary must be strings.
        :param notification: an instance of ``messages.Notification`` that contains a notification that can be included
            in a resulting message.
        :param topic: name of the Firebase topic to which the message should be sent.
        :param webpush: an instance of ``messages.WebpushConfig``. NOT IMPLEMENTED YET.
        :param dry_run: indicating whether to run the operation in dry run mode (optional). Flag for testing the request
            without actually delivering the message. Default to ``False``.

        :raises:

            ValueError is ``messages.PushNotification`` payload cannot be assembled

        :return: response from Firebase. Example of response:

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
        message = Message(
            token=device_token,
            data=data or {},
            notification=notification,
            android=android,
            webpush=webpush or {},
            apns=apns,
            topic=topic,
            condition=condition,
        )

        push_notification = self.assemble_push_notification(apns_config=apns, dry_run=dry_run, message=message)

        response = await self._send_request(
            uri=self.FCM_ENDPOINT.format(project_id=self._credentials.project_id),  # type: ignore
            json_payload=push_notification,
            headers=await self._prepare_headers(),
            response_handler=FcmPushResponseHandler(),
        )
        if not isinstance(response, FcmPushResponse):
            raise ValueError("Wrong return type, perhaps because of a response handler misuse.")
        return response

    async def push_multicast(
        self,
        device_tokens: t.Union[t.List[str], t.Tuple[str]],
        *,
        android: t.Optional[AndroidConfig] = None,
        apns: t.Optional[APNSConfig] = None,
        data: t.Optional[t.Dict[str, str]] = None,
        notification: t.Optional[Notification] = None,
        webpush: t.Optional[t.Dict[str, str]] = None,
        dry_run: bool = False,
    ) -> FcmPushMulticastResponse:
        """
        Send Multicast push notification.

        :param device_tokens: the list of device tokens to send targeted notifications to a set of instances of app.
            May contain up to 500 device tokens.
        :param android: as instance of ``messages.AndroidConfig`` that contains Android-specific options.
        :param apns: as instance of ``messages.APNSConfig`` that contains iOS-specific options.
        :param data: a dictionary of data fields. All keys and values in the dictionary must be strings.
        :param notification: an instance of ``messages.Notification`` that contains a notification that can be included
            in a resulting message.
        :param webpush: an instance of ``messages.WebpushConfig``. NOT IMPLEMENTED YET.
        :param dry_run: indicating whether to run the operation in dry run mode (optional). Flag for testing the request
            without actually delivering the message. Default to ``False``.
        """

        if len(device_tokens) > MULTICAST_MESSAGE_MAX_DEVICE_TOKENS:
            raise ValueError(
                f"A single ``messages.MulticastMessage`` may contain up to {MULTICAST_MESSAGE_MAX_DEVICE_TOKENS} "
                "device tokens."
            )

        multipart_message = MIMEMultipart("mixed")
        # Message should not write out it's own headers.
        setattr(multipart_message, "_write_headers", lambda self: None)

        for device_token in device_tokens:
            msg = MIMENonMultipart("application", "http")
            msg["Content-Transfer-Encoding"] = "binary"
            msg["Content-ID"] = self._get_request_id()
            push_notification = self.assemble_push_notification(
                apns_config=apns,
                dry_run=dry_run,
                message=Message(
                    token=device_token,
                    data=data or {},
                    notification=notification,
                    android=android,
                    webpush=webpush or {},
                    apns=apns,
                ),
            )
            body = self._serialize_batch_request(
                httpx.Request(
                    method="POST",
                    url=urljoin(
                        self.BASE_URL, self.FCM_ENDPOINT.format(project_id=self._credentials.project_id)  # type: ignore
                    ),
                    headers=await self._prepare_headers(),
                    content=json.dumps(push_notification),
                )
            )
            msg.set_payload(body)
            multipart_message.attach(msg)

        # encode the body: note that we can't use `as_string`, because it plays games with `From ` lines.
        body = serialize_mime_message(multipart_message, mangle_from=False)

        batch_response = await self._send_request(
            uri=self.FCM_BATCH_ENDPOINT,
            content=body,
            headers={"Content-Type": f"multipart/mixed; boundary={multipart_message.get_boundary()}"},
            response_handler=FcmPushMulticastResponseHandler(),
        )
        if not isinstance(batch_response, FcmPushMulticastResponse):
            raise ValueError("Wrong return type, perhaps because of a response handler misuse.")
        return batch_response

    async def _send_request(
        self,
        uri: str,
        response_handler: t.Union[FcmPushResponseHandler, FcmPushMulticastResponseHandler],
        json_payload: t.Dict[str, t.Any] = None,
        headers: t.Dict[str, str] = None,
        content: t.Union[str, bytes, t.Iterable[bytes], t.AsyncIterable[bytes]] = None,
    ) -> t.Union[FcmPushResponse, FcmPushMulticastResponse]:
        """
        Sends an HTTP call using the ``httpx`` library.

        :param uri: URI to be requested.
        :param json_payload: request JSON payload
        :param headers: request headers.
        :param content: request content
        :return: HTTP response
        """
        async with httpx.AsyncClient(base_url=self.BASE_URL) as client:
            logging.debug(
                "Requesting POST %s, payload: %s, content: %s, headers: %s",
                urljoin(self.BASE_URL, self.FCM_ENDPOINT.format(project_id=self._credentials.project_id)),
                json_payload,
                content,
                headers,
            )
            try:
                raw_fcm_response: httpx.Response = await client.post(
                    uri,
                    json=json_payload,
                    headers=headers or await self._prepare_headers(),
                    content=content,
                )
                raw_fcm_response.raise_for_status()
            except httpx.HTTPError as exc:
                response = response_handler.handle_error(exc)
            else:
                logging.debug(
                    "Response Code: %s, Time spent to make a request: %s",
                    raw_fcm_response.status_code,
                    raw_fcm_response.elapsed,
                )
                response = response_handler.handle_response(raw_fcm_response)

        return response

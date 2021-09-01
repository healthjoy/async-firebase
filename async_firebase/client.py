"""
The module houses client to communicate with FCM - Firebase Cloud Messaging (Android, iOS and Web).

Documentation for google-auth package https://google-auth.readthedocs.io/en/latest/user-guide.html that is used
to authorize request which is being made to Firebase.
"""
import logging
import typing as t
import uuid
from datetime import datetime, timedelta
from pathlib import PurePath
from urllib.parse import urljoin

import httpx
from google.auth.transport.requests import Request as GoogleRequest  # type: ignore
from google.oauth2 import service_account  # type: ignore

from .encoders import aps_encoder
from .messages import (
    AndroidConfig,
    AndroidNotification,
    APNSConfig,
    APNSPayload,
    Aps,
    ApsAlert,
    Message,
    Notification,
    PushNotification,
)
from .utils import cleanup_firebase_message, make_async


DEFAULT_TTL = 604800


class AsyncFirebaseClient:
    """Async wrapper for Firebase Cloud Messaging.

    The AsyncFirebaseClient relies on Service Account to enable us making a request. To get more about Service Account
    please refer to https://firebase.google.com/support/guides/service-accounts
    """

    BASE_URL: str = "https://fcm.googleapis.com"
    FCM_ENDPOINT: str = "/v1/projects/{project_id}/messages:send"
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
        self._credentials = credentials
        self.scopes = scopes or self.SCOPES

    def creds_from_service_account_info(self, service_account_info: t.Dict[str, str]) -> None:
        """Creates a Credentials instance from parsed service account info.

        :param service_account_info: the service account info in Google format.
        """
        self._credentials = service_account.Credentials.from_service_account_info(
            info=service_account_info, scopes=self.scopes
        )

    def creds_from_service_account_file(self, service_account_filename: t.Union[str, PurePath]) -> None:
        """Creates a Credentials instance from a service account json file.

        :param service_account_filename: the path to the service account json file.
        """
        if isinstance(service_account_filename, PurePath):
            service_account_filename = str(service_account_filename)

        logging.debug("Creating credentials from file: %s", service_account_filename)
        self._credentials = service_account.Credentials.from_service_account_file(
            filename=service_account_filename, scopes=self.scopes
        )

    @make_async
    def _get_access_token(self) -> t.Coroutine[t.Any, t.Any, t.Any]:
        """Retrieve a valid access token that can be used to authorize requests.
        :return: Access token
        """
        if self._credentials.valid:  # type: ignore
            return self._credentials.token  # type: ignore

        request = GoogleRequest()
        self._credentials.refresh(request)  # type: ignore
        logging.debug(
            "Obtained access token %s that can be used to authorize requests.", self._credentials.token  # type: ignore
        )
        return self._credentials.token  # type: ignore

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
        if data:
            data = {str(key): str(value) for key, value in data.items()}

        android_config = AndroidConfig(
            collapse_key=collapse_key,
            priority=priority,
            ttl=f"{int(ttl.total_seconds()) if isinstance(ttl, timedelta) else ttl}s",
            restricted_package_name=restricted_package_name,
            data=data or {},
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

    async def _prepare_headers(self):
        """Prepare HTTP headers that will be used to request Firebase Cloud Messaging."""
        logging.debug("Preparing HTTP headers for all the subsequent requests")
        access_token: str = await self._get_access_token()
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; UTF-8",
            "X-Request-Id": str(uuid.uuid4()),
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
    ) -> t.Dict[str, t.Any]:
        """Send push notification.

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

        # Assemble APNS custom data properly
        has_apns_config = True if apns and apns.payload else False
        if has_apns_config:
            message.apns.payload = aps_encoder(apns.payload.aps)  # type: ignore

        push_notification: t.Dict[str, t.Any] = cleanup_firebase_message(
            PushNotification(message=message, validate_only=dry_run)
        )

        if len(push_notification["message"]) == 1:
            logging.warning("No data has been provided to construct push notification payload")
            raise ValueError("``messages.PushNotification`` cannot be assembled as data has not been provided")

        response = await self._send_request(push_notification)
        return response.json()

    async def _send_request(self, payload: t.Dict[str, t.Any]) -> httpx.Response:
        """Sends an HTTP call using the ``httpx`` library.

        :param payload: request payload
        :return: HTTP response
        """
        async with httpx.AsyncClient() as client:
            url = urljoin(
                self.BASE_URL, self.FCM_ENDPOINT.format(project_id=self._credentials.project_id)  # type: ignore
            )
            logging.debug("Requesting POST %s, payload: %s", url, payload)
            response: httpx.Response = await client.post(url, json=payload, headers=await self._prepare_headers())
            logging.debug("Response Code: %s, Time spent to make a request: %s", response.status_code, response.elapsed)

        return response

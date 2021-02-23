"""The module houses client to communicate with FCM - Firebase Cloud Messaging (Android, iOS and Web).

Documentation for google-auth package https://google-auth.readthedocs.io/en/latest/user-guide.html that is used
to authorize request which is being made to Firebase.
"""
import logging
import typing as t
import uuid
from datetime import datetime
from pathlib import PurePath
from urllib.parse import urljoin

import httpx
from google.auth.transport.requests import Request as GoogleRequest  # type: ignore
from google.oauth2 import service_account  # type: ignore

from .utils import make_async, remove_null_values


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
    def build_common_message() -> t.Dict[str, t.Dict[str, t.Any]]:
        """Construct common notification message."""
        return {
            "message": {
                "android": {},
                "apns": {},
                "condition": None,
                "data": {
                    "push_id": str(uuid.uuid4()),
                    "time": datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%S"),
                },
                "notification": {},
                "token": None,
                "topic": None,
                "webpush": None,
            }
        }

    @staticmethod
    def build_android_message(  # pylint: disable=too-many-locals
        *,
        priority: str,
        ttl: int,
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
        **extra_kwargs,
    ) -> t.Tuple[t.Dict[str, t.Any], t.Dict[str, t.Any]]:
        """Constructs dictionary that will be used to customize the messages that are sent to Android device.

        :param priority: sets the priority of the message. Valid values are "normal" and "high."
        :param ttl: this parameter specifies how long (in seconds) the message should be kept in FCM storage if the
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
        :return: dictionary to included in an APNS payload, and extra-kwargs that considered unknown for Android.
        """
        if data:
            data = {str(key): str(value) for key, value in data.items()}

        notification = {
            "title": title,
            "icon": icon,
            "body": body,
            "color": color,
            "sound": sound,
            "tag": tag,
            "click_action": click_action,
            "body_loc_key": body_loc_key,
            "body_loc_args": body_loc_args,
            "title_loc_key": title_loc_key,
            "title_loc_args": title_loc_args,
        }

        android_config = {
            "priority": priority,
            "collapse_key": collapse_key,
            "restricted_package_name": restricted_package_name,
            "data": data,
            "ttl": f"{ttl}s",
            "notification": remove_null_values(notification),
        }
        return android_config, extra_kwargs

    @staticmethod
    def build_apns_message(  # pylint: disable=too-many-locals
        *,
        priority: str,
        ttl: int,
        apns_topic: str = None,
        collapse_key: str = None,
        alert: str = None,
        badge: int = None,
        sound: str = None,
        content_available: bool = True,
        category: str = None,
        thread_id: str = None,
        mutable_content: bool = True,
        custom_data: t.Dict[str, t.Any] = None,
        **extra_kwargs,
    ) -> t.Tuple[t.Dict[str, t.Any], t.Dict[str, t.Any]]:
        """Constructs dictionary that will be used to customize the messages that are sent to iOS device.

        :param priority: sets the priority of the message. On iOS, these correspond to APNs priorities 5 and 10.
        :param ttl: this parameter specifies how long (in seconds) the message should be kept in FCM storage if the
            device is offline. The maximum time to live supported is 4 weeks, and the default value is 4 weeks.
        :param apns_topic: The topic for the notification. In general, the topic is your app’s bundle ID/app ID.
            It can have a suffix based on the type of push notification.
        :param collapse_key: this parameter identifies a group of messages that can be collapsed, so that only the last
            message gets sent when delivery can be resumed.
        :param alert: A string or a ``messaging.ApsAlert`` instance (optional).
        :param badge: The value of the badge on the home screen app icon. If not specified, the badge is not changed.
            If set to 0, the badge is removed.
        :param sound: Name of the sound file to be played with the message (optional).
        :param content_available: A boolean indicating whether to configure a background update notification (optional).
        :param category: String identifier representing the message type (optional).
        :param thread_id: An app-specific string identifier for grouping messages (optional).
        :param mutable_content: A boolean indicating whether to support mutating notifications at the client using app
            extensions (optional).
        :param custom_data: A dict of custom key-value pairs to be included in the Aps dictionary (optional).
        :return: dictionary to included in an APNS payload, and extra-kwargs that considered unknown for APNS.
        """

        apns_headers = {
            "apns-expiration": str(int(datetime.utcnow().timestamp()) + ttl),
            "apns-priority": str(10 if priority == "high" else 5),
        }
        if apns_topic:
            apns_headers["apns-topic"] = apns_topic
        if collapse_key:
            apns_headers["apns-collapse-id"] = str(collapse_key)

        apns_config = {
            "headers": apns_headers,
            "payload": {
                "aps": {
                    "alert": alert,
                    "badge": badge,
                    "sound": "default" if alert and sound is None else sound,
                    "content_available": content_available,
                    "category": category,
                    "thread_id": thread_id,
                    "mutable_content": mutable_content,
                    "custom_data": custom_data,
                }
            },
        }
        return apns_config, extra_kwargs

    async def _prepare_headers(self):
        """Prepare HTTP headers that will be used to request Firebase Cloud Messaging."""
        logging.debug("Preparing HTTP headers for all the subsequent requests")
        access_token: str = await self._get_access_token()
        return {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json; UTF-8",
        }

    async def push(  # pylint: disable=too-many-locals
        self,
        device_token: str,
        *,
        notification_title: str = None,
        notification_body: str = None,
        notification_data: t.Dict[str, t.Any] = None,
        silent: bool = False,
        category: str = None,
        collapse_key: str = None,
        ttl: int = 604800,
        dry_run: bool = False,
        **kwargs,
    ) -> t.Dict[str, t.Any]:
        """Send push notification.

        :param device_token: device token allows to send targeted notifications to a particular instance of app.
        :param notification_title: the notification's title.
        :param notification_body: the notification's body text also known as alert text.
        :param notification_data: arbitrary key/value payload. The key should not be a reserved word ("from",
            "message_type", or any word starting with "google" or "gcm")
        :param silent: ``True`` to indicate that the notification should be silent (optional). Default to ``False``.
        :param category: string identifier representing the message type (optional).
        :param collapse_key: collapse key string for the message (optional). This is an identifier for a group of
            messages that can be collapsed, so that only the last message is sent when delivery can be resumed.
            A maximum of 4 different collapse keys may be active at a given time.
        :param ttl: the time-to-live duration of the message (optional). This can be specified as a numeric seconds
            value or a ``datetime.timedelta`` instance. Default 7 days.
        :param dry_run: indicating whether to run the operation in dry run mode (optional). Flag for testing the request
            without actually delivering the message. Default to ``False``.
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
        priority = kwargs.pop("priority", "normal")
        if silent:
            kwargs.pop("alert", None)

        fcm_message: t.Dict[str, t.Any] = self.build_common_message()
        fcm_message["message"]["token"] = device_token
        fcm_message["message"]["notification"] = {
            "title": notification_title,
            "body": notification_body,
        }
        if notification_data:
            fcm_message["message"]["data"].update(notification_data)

        fcm_message["message"]["android"], unknown_kwargs = self.build_android_message(
            priority=priority,
            ttl=ttl,
            collapse_key=collapse_key,
            **kwargs,
        )
        fcm_message["message"]["apns"], unknown_kwargs = self.build_apns_message(
            priority=priority,
            ttl=ttl,
            collapse_key=collapse_key,
            category=category,
            **kwargs,
        )
        if unknown_kwargs:
            fcm_message["message"]["data"].update(unknown_kwargs)

        fcm_message["message"] = remove_null_values(fcm_message["message"])

        if dry_run:
            fcm_message["validate_only"] = True

        async with httpx.AsyncClient() as client:
            url = urljoin(
                self.BASE_URL, self.FCM_ENDPOINT.format(project_id=self._credentials.project_id)  # type: ignore
            )
            logging.debug("Requesting POST %s", url)
            response: httpx.Response = await client.post(url, json=fcm_message, headers=await self._prepare_headers())

        return response.json()

"""
The module houses client to communicate with FCM - Firebase Cloud Messaging (Android, iOS and Web).

Documentation for google-auth package https://google-auth.readthedocs.io/en/latest/user-guide.html that is used
to authorize request which is being made to Firebase.
"""

import asyncio
import collections
import logging
import typing as t
from dataclasses import replace

from async_firebase.base import AsyncClientBase, RequestLimits, RequestTimeout  # noqa: F401
from async_firebase.encoders import aps_encoder
from async_firebase.errors import AsyncFirebaseError
from async_firebase.messages import (
    AndroidConfig,
    APNSConfig,
    FCMBatchResponse,
    FCMResponse,
    Message,
    MulticastMessage,
    PushNotification,
    TopicManagementResponse,
    WebpushConfig,
)
from async_firebase.utils import (
    FCMResponseHandler,
    TopicManagementResponseHandler,
    cleanup_firebase_message,
)


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
        if apns_config and apns_config.payload:
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

    # Backward-compatible wrappers delegating to classmethod constructors on the config dataclasses.
    # Prefer calling AndroidConfig.build(), APNSConfig.build(), WebpushConfig.build() directly.
    build_android_config = staticmethod(AndroidConfig.build)
    build_apns_config = staticmethod(APNSConfig.build)
    build_webpush_config = staticmethod(WebpushConfig.build)

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

    async def send_each(
        self,
        messages: t.Union[t.List[Message], t.Tuple[Message]],
        *,
        dry_run: bool = False,
    ) -> FCMBatchResponse:
        if len(messages) > BATCH_MAX_MESSAGES:
            raise ValueError(f"Can not send more than {BATCH_MAX_MESSAGES} messages in a single batch")

        push_notifications = [
            self.assemble_push_notification(apns_config=message.apns, dry_run=dry_run, message=message)
            for message in messages
        ]

        request_tasks: t.Collection[collections.abc.Awaitable] = [
            self.send_request(
                uri=self.FCM_ENDPOINT.format(project_id=self._credentials.project_id),  # type: ignore
                json_payload=push_notification,
                response_handler=FCMResponseHandler(),
            )
            for push_notification in push_notifications
        ]
        results = await asyncio.gather(*request_tasks, return_exceptions=True)
        fcm_responses: t.List[FCMResponse] = []
        for result in results:
            if isinstance(result, FCMResponse):
                fcm_responses.append(result)
            elif isinstance(result, AsyncFirebaseError):
                fcm_responses.append(FCMResponse(exception=result))
            elif isinstance(result, BaseException):
                fcm_responses.append(
                    FCMResponse(
                        exception=AsyncFirebaseError(
                            code="UNKNOWN",
                            message=str(result),
                            cause=result if isinstance(result, Exception) else None,
                        )
                    )
                )
            else:
                fcm_responses.append(result)
        return FCMBatchResponse(responses=fcm_responses)

    async def send_each_for_multicast(
        self,
        multicast_message: MulticastMessage,
        *,
        dry_run: bool = False,
    ) -> FCMBatchResponse:
        if len(multicast_message.tokens) > MULTICAST_MESSAGE_MAX_DEVICE_TOKENS:
            raise ValueError(
                f"A single ``messages.MulticastMessage`` may contain up to {MULTICAST_MESSAGE_MAX_DEVICE_TOKENS} "
                "device tokens."
            )

        return await self.send_each(multicast_message.to_messages(), dry_run=dry_run)

    async def _make_topic_management_request(
        self, device_tokens: t.List[str], topic_name: str, action: str
    ) -> TopicManagementResponse:
        payload = {
            "to": f"/topics/{topic_name}",
            "registration_tokens": device_tokens,
        }
        response = await self.send_iid_request(
            uri=action,
            json_payload=payload,
            response_handler=TopicManagementResponseHandler(),
        )
        return response

    async def subscribe_devices_to_topic(self, device_tokens: t.List[str], topic_name: str) -> TopicManagementResponse:
        """
        Subscribes devices to the topic.

        :param device_tokens: devices ids to be subscribed.
        :param topic_name: name of the topic.
        :returns: Instance of messages.TopicManagementResponse.
        """
        return await self._make_topic_management_request(
            device_tokens=device_tokens, topic_name=topic_name, action=self.TOPIC_ADD_ACTION
        )

    async def unsubscribe_devices_from_topic(
        self, device_tokens: t.List[str], topic_name: str
    ) -> TopicManagementResponse:
        """
        Unsubscribes devices from the topic.

        :param device_tokens: devices ids to be unsubscribed.
        :param topic_name: name of the topic.
        :returns: Instance of messages.TopicManagementResponse.
        """
        return await self._make_topic_management_request(
            device_tokens=device_tokens, topic_name=topic_name, action=self.TOPIC_REMOVE_ACTION
        )

"""
The module houses client to communicate with FCM - Firebase Cloud Messaging (Android, iOS and Web).

Documentation for google-auth package https://google-auth.readthedocs.io/en/latest/user-guide.html that is used
to authorize request which is being made to Firebase.
"""

import asyncio
import collections
import typing as t

from async_firebase.base import AsyncClientBase, RequestLimits, RequestTimeout  # noqa: F401
from async_firebase.errors import AsyncFirebaseError
from async_firebase.messages import (
    AndroidConfig,
    APNSConfig,
    FCMBatchResponse,
    FCMResponse,
    Message,
    MulticastMessage,
    TopicManagementResponse,
    WebpushConfig,
)
from async_firebase.serialization import serialize_message


BATCH_MAX_MESSAGES = MULTICAST_MESSAGE_MAX_DEVICE_TOKENS = 500


class AsyncFirebaseClient(AsyncClientBase):
    """Async wrapper for Firebase Cloud Messaging.

    The AsyncFirebaseClient relies on Service Account to enable us making a request. To get more about Service Account
    please refer to https://firebase.google.com/support/guides/service-accounts
    """

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
        push_notification = serialize_message(message, dry_run=dry_run)
        return await self.send_fcm_request(
            uri=self.FCM_ENDPOINT.format(project_id=self._credentials.project_id),
            json_payload=push_notification,
        )

    async def send_each(
        self,
        messages: t.Union[t.List[Message], t.Tuple[Message]],
        *,
        dry_run: bool = False,
    ) -> FCMBatchResponse:
        if len(messages) > BATCH_MAX_MESSAGES:
            raise ValueError(f"Can not send more than {BATCH_MAX_MESSAGES} messages in a single batch")

        push_notifications = [serialize_message(msg, dry_run=dry_run) for msg in messages]

        request_tasks: t.Collection[collections.abc.Awaitable] = [
            self.send_fcm_request(
                uri=self.FCM_ENDPOINT.format(project_id=self._credentials.project_id),
                json_payload=push_notification,
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
        return await self.send_topic_request(
            uri=action,
            json_payload=payload,
            extra_headers=self.IID_HEADERS,
        )

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

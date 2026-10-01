"""
The module houses client to communicate with FCM - Firebase Cloud Messaging (Android, iOS and Web).

Documentation for google-auth package https://google-auth.readthedocs.io/en/latest/user-guide.html that is used
to authorize request which is being made to Firebase.
"""

import asyncio
import collections
import re
import typing as t
import warnings

from async_firebase.base import AsyncClientBase, RequestLimits, RequestTimeout  # noqa: F401
from async_firebase.errors import AsyncFirebaseError, FcmErrorCode
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
from async_firebase.utils import join_url


BATCH_MAX_MESSAGES = MULTICAST_MESSAGE_MAX_DEVICE_TOKENS = 500
TOPIC_MANAGEMENT_MAX_DEVICE_TOKENS = 1000
TOPIC_MANAGEMENT_MAX_CONCURRENCY = 100
TOPIC_PREFIX = "/topics/"
TOPIC_NAME_PATTERN = re.compile(r"[a-zA-Z0-9_.~%-]+")
_ALREADY_SUBSCRIBED_REASONS = frozenset({FcmErrorCode.ALREADY_EXISTS.value, FcmErrorCode.CONFLICT.value})


def _validate_device_tokens(device_tokens: t.Sequence[str]) -> None:
    if isinstance(device_tokens, str) or not isinstance(device_tokens, collections.abc.Sequence):
        raise ValueError("device_tokens must be a sequence of strings")
    if not device_tokens:
        raise ValueError("device_tokens must not be empty")
    if not all(isinstance(device_token, str) and device_token for device_token in device_tokens):
        raise ValueError("device_tokens must contain only non-empty strings")
    if len(device_tokens) > TOPIC_MANAGEMENT_MAX_DEVICE_TOKENS:
        raise ValueError(
            f"Can not manage topic subscriptions for more than {TOPIC_MANAGEMENT_MAX_DEVICE_TOKENS} device tokens "
            "in a single call"
        )


def _normalize_topic_name(topic_name: str) -> str:
    """Strip the optional ``/topics/`` prefix and validate what remains."""
    if not isinstance(topic_name, str) or not topic_name:
        raise ValueError("topic_name must be a non-empty string")
    topic = topic_name.removeprefix(TOPIC_PREFIX)
    if not TOPIC_NAME_PATTERN.fullmatch(topic):
        raise ValueError(f"Malformed topic name: {topic_name!r}")
    return topic


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
        # The ``tokens``/``fids`` count is validated at ``MulticastMessage`` construction time.
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

    def _topic_subscriptions_url(self, device_token: str, *parts: str, params: t.Dict[str, str]) -> str:
        registrations_uri = self.FCM_REGISTRATIONS_ENDPOINT.format(project_id=self._credentials.project_id)
        return join_url(self.BASE_URL, registrations_uri, device_token, "topicSubscriptions", *parts, params=params)

    def _topic_management_concurrency(self) -> int:
        max_connections = self._request_limits.max_connections
        if not max_connections:
            return TOPIC_MANAGEMENT_MAX_CONCURRENCY
        return min(TOPIC_MANAGEMENT_MAX_CONCURRENCY, max_connections)

    async def _subscribe_device_to_topic(self, device_token: str, topic: str) -> t.Optional[str]:
        url = self._topic_subscriptions_url(device_token, params={"topic_name": topic})
        reason = await self._send_topic_subscription_request("POST", url, json_payload={})
        return None if reason in _ALREADY_SUBSCRIBED_REASONS else reason

    async def _unsubscribe_device_from_topic(self, device_token: str, topic: str) -> t.Optional[str]:
        url = self._topic_subscriptions_url(device_token, topic, params={"allow_missing": "true"})
        return await self._send_topic_subscription_request("DELETE", url)

    async def _manage_topic_subscriptions(
        self,
        manage_subscription: t.Callable[[str, str], t.Awaitable[t.Optional[str]]],
        device_tokens: t.Sequence[str],
        topic_name: str,
    ) -> TopicManagementResponse:
        _validate_device_tokens(device_tokens)
        topic = _normalize_topic_name(topic_name)
        semaphore = asyncio.Semaphore(self._topic_management_concurrency())

        async def manage_with_limit(device_token: str) -> t.Optional[str]:
            async with semaphore:
                return await manage_subscription(device_token, topic)

        tasks = [asyncio.create_task(manage_with_limit(device_token)) for device_token in device_tokens]
        try:
            reasons = await asyncio.gather(*tasks)
        except Exception:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            raise
        return TopicManagementResponse.from_error_reasons(reasons)

    async def subscribe_devices_to_topic(
        self, device_tokens: t.Sequence[str], topic_name: str
    ) -> TopicManagementResponse:
        """
        Subscribes devices to the topic using the FCM v1 API.

        One request is made per device token. Failures, including authentication errors, are reported per token in
        ``TopicManagementResponse.errors``. A device token that is already subscribed counts as a success.

        :param device_tokens: devices ids to be subscribed, up to 1000.
        :param topic_name: name of the topic, optionally prefixed with ``/topics/``.
        :raises: ValueError if the device tokens or the topic name are invalid.
        :returns: Instance of messages.TopicManagementResponse.
        """
        return await self._manage_topic_subscriptions(self._subscribe_device_to_topic, device_tokens, topic_name)

    async def unsubscribe_devices_from_topic(
        self, device_tokens: t.Sequence[str], topic_name: str
    ) -> TopicManagementResponse:
        """
        Unsubscribes devices from the topic using the FCM v1 API.

        One request is made per device token. Failures, including authentication errors, are reported per token in
        ``TopicManagementResponse.errors``. A device token that is not subscribed counts as a success.

        :param device_tokens: devices ids to be unsubscribed, up to 1000.
        :param topic_name: name of the topic, optionally prefixed with ``/topics/``.
        :raises: ValueError if the device tokens or the topic name are invalid.
        :returns: Instance of messages.TopicManagementResponse.
        """
        return await self._manage_topic_subscriptions(self._unsubscribe_device_from_topic, device_tokens, topic_name)

    async def subscribe_devices_to_topic_legacy(
        self, device_tokens: t.List[str], topic_name: str
    ) -> TopicManagementResponse:
        """
        Subscribes devices to the topic using the legacy Instance ID API.

        Deprecated. Use ``subscribe_devices_to_topic`` instead.

        :param device_tokens: devices ids to be subscribed.
        :param topic_name: name of the topic.
        :returns: Instance of messages.TopicManagementResponse.
        """
        warnings.warn(
            "subscribe_devices_to_topic_legacy is deprecated. Use subscribe_devices_to_topic instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return await self._make_topic_management_request(
            device_tokens=device_tokens, topic_name=topic_name, action=self.TOPIC_ADD_ACTION
        )

    async def unsubscribe_devices_from_topic_legacy(
        self, device_tokens: t.List[str], topic_name: str
    ) -> TopicManagementResponse:
        """
        Unsubscribes devices from the topic using the legacy Instance ID API.

        Deprecated. Use ``unsubscribe_devices_from_topic`` instead.

        :param device_tokens: devices ids to be unsubscribed.
        :param topic_name: name of the topic.
        :returns: Instance of messages.TopicManagementResponse.
        """
        warnings.warn(
            "unsubscribe_devices_from_topic_legacy is deprecated. Use unsubscribe_devices_from_topic instead.",
            DeprecationWarning,
            stacklevel=2,
        )
        return await self._make_topic_management_request(
            device_tokens=device_tokens, topic_name=topic_name, action=self.TOPIC_REMOVE_ACTION
        )

"""Integration tests that call the real FCM v1 topic subscriptions API.

No real device is available, so the requests use a made-up registration token. FCM may accept or reject it;
either way it only answers after routing and authorizing the request. The tests therefore confirm the endpoint,
HTTP method and credentials are right and that FCM's answer is handled, but not the success or
"already subscribed" paths for a real device.
"""

import httpx
import pytest

from tests.integration import requires_firebase_credentials


pytestmark = [pytest.mark.asyncio, pytest.mark.integration, requires_firebase_credentials]

_TEST_TOPIC = "async-firebase-integration-test"
# Shaped like a real registration token, including the ":" that has to be escaped in the request path.
_MADE_UP_DEVICE_TOKEN = "async-firebase-integration-test:" + "x" * 140


def _assert_answered_by_fcm(error):
    """Assert the request was routed, authorized and answered by the FCM API.

    ``None`` means FCM accepted the request. An error must be a JSON Google API error: a non-JSON body would mean
    a wrong endpoint, and 401/403 would mean the credentials or OAuth scope cannot manage topic subscriptions.
    """
    if error is None:
        return
    assert isinstance(error, httpx.HTTPStatusError), f"The request did not complete: {error!r}"
    response = error.response
    assert response.status_code not in (httpx.codes.UNAUTHORIZED, httpx.codes.FORBIDDEN), response.text
    try:
        body = response.json()
    except ValueError:
        pytest.fail(f"FCM answered {response.status_code} with a non-JSON body, so the endpoint is likely wrong")
    error_data = body.get("error") if isinstance(body, dict) else None
    assert isinstance(error_data, dict) and error_data.get("status"), f"Not a Google API error: {body!r}"


@pytest.mark.parametrize(
    "method, extra_path, params, json_payload",
    (
        ("POST", (), {"topic_name": _TEST_TOPIC}, {}),
        ("DELETE", (_TEST_TOPIC,), {"allow_missing": "true"}, None),
    ),
    ids=("subscribe", "unsubscribe"),
)
async def test_topic_subscription_request_is_answered_by_fcm(fcm_client, method, extra_path, params, json_payload):
    url = fcm_client._topic_subscriptions_url(_MADE_UP_DEVICE_TOKEN, *extra_path, params=params)
    headers = await fcm_client.prepare_headers()

    error = await fcm_client._send_topic_subscription_request(method, url, headers, json_payload=json_payload)

    _assert_answered_by_fcm(error)


@pytest.mark.parametrize("method_name", ("subscribe_to_topic", "unsubscribe_from_topic"))
async def test_topic_management_reports_one_outcome_per_token(fcm_client, method_name):
    response = await getattr(fcm_client, method_name)(device_tokens=[_MADE_UP_DEVICE_TOKEN], topic_name=_TEST_TOPIC)

    assert response.exception is None
    assert response.success_count + response.failure_count == 1
    assert [error.reason for error in response.errors if error.reason in ("UNAUTHENTICATED", "PERMISSION_DENIED")] == []

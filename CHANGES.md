# Changelog

## 6.1.2
* Relax `google-auth` constraint from `~=2.38.0` to `>=2.38.0,<3.0.0`, allowing consumers to pick up patch and minor releases of `google-auth` (currently `2.52.0`) without a release of this package. No API changes.

## 6.1.1
* Resolve a security concern by updating `cryptography` package to `46.0.7`.
  * [Medium] cryptography vulnerable to buffer overflow if non-contiguous buffers were passed to APIs ([CVE-2026-39892](https://nvd.nist.gov/vuln/detail/CVE-2026-39892))

## 6.1.0
* ``AndroidConfig.build()`` and ``APNSConfig.build()`` now support data-only FCM messages. When no notification/alert fields are provided, the builder omits the ``notification`` (Android) or ``alert`` (APNS) from the payload, producing a clean data-only message.
* ``AndroidConfig.build()`` ``visibility`` parameter default changed from ``Visibility.PRIVATE`` to ``None``. FCM applies ``PRIVATE`` server-side when omitted, so wire behavior is unchanged.

## 6.0.2
* [FIX] Correct FCM wire-format for ``AndroidNotification`` enum fields to match the official ``firebase-admin-python`` SDK:
  * ``visibility``: send ``"PRIVATE"`` instead of ``"VISIBILITY_PRIVATE"`` (fixes ``InvalidArgumentError`` from FCM API).
  * ``priority``: use wire-format key ``"notification_priority"`` instead of ``"priority"``.
  * ``event_timestamp``: use wire-format key ``"event_time"`` instead of ``"event_timestamp"``.
  * Remove stale dataclass field names (``priority``, ``event_timestamp``, ``vibrate_timings_millis``) that leaked into the serialized payload alongside their correctly-keyed overrides.

## 6.0.1
* [FIX] Fix race condition in lazy HTTP client initialization. Concurrent coroutines could previously create multiple ``httpx.AsyncClient`` instances, orphaning connections. The synchronous ``_client`` property is replaced with an async ``_get_client()`` method guarded by ``asyncio.Lock``, and ``close()`` now acquires the same lock to prevent races between teardown and initialization.

## 6.0.0
FCM message parity with the official ``firebase-admin-python`` SDK.

### New dataclasses
* ``LightSettings`` — Android LED blink configuration (``color``, ``light_on_duration_millis``, ``light_off_duration_millis``).
* ``CriticalSound`` — iOS critical alert sound (``name``, ``critical``, ``volume``).
* ``AndroidFCMOptions`` — Android-specific FCM options (``analytics_label``).
* ``APNSFCMOptions`` — APNS-specific FCM options (``analytics_label``, ``image``).
* ``AndroidNotificationPriority`` — enum for notification-level UI priority (``default``, ``min``, ``low``, ``high``, ``max``).

### New fields on existing dataclasses
* ``AndroidNotification``: ``image``, ``ticker``, ``sticky``, ``event_timestamp``, ``local_only``, ``priority``, ``vibrate_timings_millis``, ``default_vibrate_timings``, ``default_sound``, ``light_settings``, ``default_light_settings``.
* ``AndroidConfig``: ``fcm_options``, ``direct_boot_ok``, ``bandwidth_constrained_ok``, ``restricted_satellite_ok``.
* ``APNSConfig``: ``fcm_options``, ``live_activity_token``.
* ``ApsAlert``: ``subtitle``, ``custom_data``.
* ``Aps.sound`` now accepts ``CriticalSound`` in addition to ``str``.

### Updated ``build()`` classmethods
* ``AndroidConfig.build()`` accepts all new ``AndroidNotification`` and ``AndroidConfig`` fields.
* ``APNSConfig.build()`` accepts ``subtitle``, ``sound`` as ``CriticalSound``, ``fcm_options``, ``live_activity_token``.
* ``WebpushConfig.build()`` ``vibrate`` parameter type corrected to ``List[int]``.

### Serialization
* New dedicated encoders in ``serialization`` module: ``encode_light_settings``, ``encode_android_notification``, ``encode_critical_sound``.
* ``aps_encoder`` now handles ``ApsAlert.subtitle``, ``ApsAlert.custom_data``, and ``CriticalSound``.
* ``serialize_message`` applies Android notification encoding (enum prefixing, timestamp formatting, duration conversion) before the generic cleanup pass.

### Breaking changes
* [BREAKING] ``Visibility`` changed from ``IntEnum`` to string ``Enum`` (values: ``"private"``, ``"public"``, ``"secret"``). Wire format now serializes as ``PRIVATE`` etc.
* [BREAKING] ``WebpushNotification.vibrate`` type changed from ``str`` to ``Optional[List[int]]``.
* [BREAKING] ``NotificationProxy`` enum values now serialize as uppercase (``ALLOW``, ``DENY``, ``IF_PRIORITY_LOWERED``) in the wire format.

## 5.2.0
* Extract error mapping and response handling into dedicated ``responses`` module. All HTTP-to-domain-error resolution — lookup tables, FCM-specific error detection, transport error mapping — now lives in ``async_firebase.responses`` with four typed public functions: ``handle_fcm_response``, ``handle_fcm_error``, ``handle_topic_response``, ``handle_topic_error``.
* Extract payload serialization into dedicated ``serialization`` module. Message-to-JSON assembly — APNS encoding, recursive null stripping, validation — now lives in ``async_firebase.serialization`` with a single entry point: ``serialize_message(message, dry_run)``.
* Absorb ``encoders.py`` into ``serialization`` module. The ``aps_encoder`` function is now part of ``async_firebase.serialization``.
* Split generic ``_send_request(response_handler)`` in ``AsyncClientBase`` into two statically typed methods: ``send_fcm_request`` → ``FCMResponse`` and ``send_topic_request`` → ``TopicManagementResponse``. Eliminates runtime ``isinstance`` type guards and handler instantiation ceremony.
* Simplify ``client.py``: remove ``assemble_push_notification`` static method (replaced by ``serialize_message``), drop redundant ``apns_config`` parameter that was always ``message.apns``.
* Clean up ``utils.py``: now contains only ``join_url`` with zero dependencies on library code (pure inward dependency direction).
* Backward-compatible handler classes ``FCMResponseHandler`` and ``TopicManagementResponseHandler`` remain available in ``async_firebase.responses`` for external consumers.

## 5.1.1
* Address **CVE-2026-30922**: Denial of Service in pyasn1 via unbounded recursion in the decoder. The transitive dependency ``pyasn1`` is now pinned to 0.6.3+ which includes the fix.
* Fix CI/CD workflow issues and update outdated actions.

## 5.1.0
* [BREAKING] Remove deprecated ``send_all`` and ``send_multicast`` methods. Use ``send_each`` and ``send_each_for_multicast`` instead.
* Add async context manager support (``async with AsyncFirebaseClient() as client:``) for proper resource cleanup.
* Add concurrency-safe token refresh with ``asyncio.Lock`` to prevent duplicate refresh requests.
* Move ``build_android_config``, ``build_apns_config``, ``build_webpush_config`` to classmethod constructors on their respective config dataclasses (``AndroidConfig.build()``, ``APNSConfig.build()``, ``WebpushConfig.build()``). The old ``client.build_*`` methods still work as backward-compatible wrappers.
* Extract credential management from ``AsyncClientBase`` into dedicated ``CredentialManager`` class.
* Consolidate ``send_request`` and ``send_iid_request`` into unified interface with ``base_url`` and ``extra_headers`` parameters.
* Convert ``FCMResponse``, ``FCMBatchResponse``, ``TopicManagementResponse``, and ``TopicManagementErrorInfo`` to dataclasses.
* Simplify exception hierarchy: subclasses now declare ``default_code`` class attribute instead of duplicating ``__init__``.
* Replace boolean-chain (``and``/``or``) control flow in error dispatch with explicit ``if``/``elif``/``else``.
* Add ``logging.warning`` when FCM error response cannot be parsed as JSON.
* Add ``__all__`` to ``async_firebase/__init__.py`` and re-export commonly used types (``Message``, ``AndroidConfig``, ``APNSConfig``, etc.).
* Replace magic numbers with named constants (``APNS_PRIORITY_HIGH``, ``APNS_PRIORITY_NORMAL``, ``FCM_ERROR_TYPE_PREFIX``).
* Fix ``remove_null_values`` to use identity check (``is not None``) instead of equality against mutable list.
* Use ``return_exceptions=True`` in ``asyncio.gather`` within ``send_each`` to prevent one failure from losing all results.
* Standardize string formatting on f-strings throughout the codebase.
* Remove dead code: ``FCMBatchResponseHandler``, ``serialize_mime_message``, ``serialize_batch_request``, MIME-related imports, and ``FCM_BATCH_ENDPOINT``.
* Update ``README.md``: remove outdated pre-3.0 examples, use ``async with`` context manager and ``Config.build()`` classmethods in all examples, fix deprecated ``datetime.utcnow()`` usage.
* Improve test coverage 89% → 99%

## 5.0.0
* [BREAKING] Drop support of **Python 3.9** and update dependencies.
* Add support of **Python 3.14**.

## 4.1.0
* Extend ``async_firebase.messages.AndroidNotification`` object with new attribute ``proxy``. The attribute sets whether the notification can be proxied. Must be one of ``allow``, ``deny``, or ``if_priority_lowered``.

## 4.0.0
* [BREAKING] Drop support of **Python 3.8** and update dependencies.

## 3.12.1
* [FIX] `google-auth` deals with offset-maive datetime objct when validating token. Method `async_firebase.base.AsyncClientBase._get_access_token` is adjusted to replace tzinfo with `None`.

## 3.12.0
* Extend ``async_firebase.messages.AndroidNotification`` object with new attribute ``Visibility``. The attribute sets different visibility levels of a notification.

## 3.11.0
* [MINOR] Usage of `datetime.utcnow()` is deprecated in Python 3.12, so it was replaced with a recommended way, which is `datetime.now(timezone.utc)`

## 3.10.0
* `async_firebase` now works with python 3.13

## 3.9.0
* Add ability to say that HTTP/2 protocol should be used when making request. Please find an example below:
```python

client = AsyncFirebaseClient(use_http2=True)
```

## 3.8.0
* Endow ``async_firebase.messages.MulticastMessage`` with the ability to set FCM options.

## 3.7.0
* `async-firebase` has been allowed to perform basic topic management tasks from the server side. Given their registration token(s), you can now subscribe and unsubscribe client app instances in bulk using server logic. You can subscribe client app instances to any existing topic, or you can create a new topic.

## 3.6.3
* [FIX] The ``join_url`` util has been tuned to encode the URL properly when the path is present. That led to the invalid URL being built.

## 3.6.2
* Resolve a couple of security concerns by updating `cryptography` package to `42.0.4`.
  * [High] cryptography NULL pointer dereference with pkcs12.serialize_key_and_certificates when called with a non-matching certificate and private key and an hmac_hash override
  * [High] Python Cryptography package vulnerable to Bleichenbacher timing oracle attack
  * [Moderate] Null pointer dereference in PKCS12 parsing
  * [Moderate] cryptography vulnerable to NULL-dereference when loading PKCS7 certificates

## 3.6.1
* Remove unintended quoting of the column char in the API URLs

## 3.6.0
* Introduce send_each and send_each_for_multicast methods
* Add deprecation warnings to send_all and send_multicast methods, because they use the API that
  Google may deprecate soon. The newly introduced methods should be safe to use.

## 3.5.0
* [BREAKING] Drop support of **Python 3.7**

## 3.4.1
* [FIX] The batch URL is composed incorrectly, which causes an HTTP 404 response to be received.

## 3.4.0
* Refactored  ``async_firebase.base.AsyncClientBase`` to take advantage of connection pool. So the HTTP client will be created once during class ``async_firebase.client.AsyncFirebaseClient`` instantiation.

## 3.3.0
* `async_firebase` now works with python 3.12

## 3.2.0
* ``AsyncFirebaseClient`` empower with advanced features to configure request behaviour such as timeout, or connection pooling.
Example:
```python

from async_firebase.client import AsyncFirebaseClient, RequestTimeout

# This will disable timeout
client = AsyncFirebaseClient(..., request_timeout=RequestTimeout(None))
client.send(...)
```

## 3.1.1
* [FIX] The push notification could not be sent to topic because ``messages.Message.token`` is declared as required attribute though it should be optional.
``messages.Message.token`` turned into Optional attribute.

## 3.1.0
* The limit on the number of messages (>= 500) that can be sent using the ``send_all`` method has been restored.

## 3.0.0
Remastering client interface
* [BREAKING] The methods ``push`` and ``push_multicast`` renamed to ``send`` and ``send_multicast`` accordingly.
* [BREAKING] The signatures of the methods ``send`` and ``send_multicast`` have been changed.
  * Method ``send`` accepts instance of ``messages.Message`` and returns ``messages.FCMBatchResponse``
  * Method ``send_multicast`` accepts instance of ``messages.MulticastMessage`` and returns ``messages.FCMBatchResponse``
* New method ``send_all`` to send messages in a single batch has been added. It takes a list of ``messages.Message`` instances and returns ``messages.FCMBatchResponse``.
* ``README.md`` has been updated to highlight different in interfaces for versions prior **3.x** and after
* Improved naming:
  * ``messages.FcmPushMulticastResponse`` to ``messages.FCMBatchResponse``
  * ``messages.FcmPushResponse`` to ``messages.FCMResponse``
  * ``utils.FcmReponseType`` to ``utils.FCMResponseType``
  * ``utils.FcmResponseHandler`` to ``utils.FCMResponseHandlerBase``
  * ``utils.FcmPushResponseHandler`` to ``utils.FCMResponseHandler``
  * ``utils.FcmPushMulticastResponseHandler`` to ``utils.FCMBatchResponseHandler``
* Type annotations and doc string were updated according to new naming.

## 2.7.0
* Class ``AsyncFirebaseClient`` has been refactored. Communication related code extracted into base class.

## 2.6.1
* ``async_firebase.encoders.aps_encoder`` no longer clears ``custom_data`` dictionary, as this causes subsequent notifications to not get any content in ``custom_data`` dictionary.

## 2.6.0
* Add object for sending Web Push.

## 2.5.1
* Fix WebPush type annotation

## 2.5.0
* Adds field ``notification_count`` to ``AndroidNotification`` message.

## 2.4.0
* [BREAKING] Drop support of **Python 3.6**
* Update dependencies
* Make implicit optional type hints PEP 484 compliant.

## 2.3.0
Method ``client.build_android_config`` has been adjusted, so when ``data`` parameter is passed but the value is not set (equal to `None`),
turn in into ``"null"``

## 2.2.0
async_firebase now works with **Python 3.11**
* Removes ``asynctest`` as it is no longer maintained [ref](https://github.com/Martiusweb/asynctest/issues/158#issuecomment-785872568)

## 2.1.0
  * ``messages.Notification`` object now supports attribute ``image`` that allows to set image url of the notification

## 2.0.3
A few new error types have been added to support the errors that FCM API may return:
- InvalidArgumentError
- FailedPreconditionError
- OutOfRangeError
- UnauthenticatedError
- PermissionDeniedError
- NotFoundError
- AbortedError
- AlreadyExistsError
- ConflictError
- ResourceExhaustedError
- CancelledError
- DataLossError
- UnknownError
- InternalError
- UnavailableError
- DeadlineExceededError

## 2.0.2
  * Adjust type annotations for some errors:

  **async_firebase/errors.py**
```python

class AsyncFirebaseError(BaseAsyncFirebaseError):
    """A prototype for all AF Errors.

    This error and its subtypes and the reason to rise them are consistent with Google's errors,
    that may be found in `firebase-admin-python` in `firebase_admin.exceptions module`.
    """

    def __init__(
        self,
        code: str,
        message: str,
        <<< cause: t.Optional[Exception] = None,
        >>> cause: t.Union[httpx.HTTPStatusError, httpx.RequestError, None] = None,
        http_response: t.Optional[httpx.Response] = None,
    ):
```

    **async_firebase/messages.py**
```python
class FcmPushResponse:
    """The response received from an individual batched request to the FCM API.

    The interface of this object is compatible with SendResponse object of
    the Google's firebase-admin-python package.
    """

    def __init__(
        self,
        fcm_response: t.Optional[t.Dict[str, str]] = None,
        <<< exception: t.Optional[Exception] = None
        >>> exception: t.Optional[AsyncFirebaseError] = None
    ):
```

## 2.0.1
  * Fix ``TypeError`` on create ``AsyncFirebaseError`` subclass instance

## 2.0.0
  * `push` method now returns a `FcmPushResponse` object, that has a fully compatible interface with SendResponse object of the Google's firebase-admin-python package.
  * `push_multicast` method now returns a `FcmPushMulticastResponse` object, that has a fully compatible interface with BatchResponse object of the Google's firebase-admin-python package.
  * The aforementioned methods may still rise exceptions when assembling the message for the request.
  * A bunch of exceptions has been added.

## 1.9.1

  * [FIX] Invalid batch requests fixed in``push_multicast`` method.
  * [FIX] Data mutation issues that lead to unexpected behaviour fixed in ``assemble_push_notification`` method.
  * Message ``messages.MulticastMessage`` was deprecated as it's no longer used.

## 1.9.0

  * Add support of [MulticastMessage](https://firebase.google.com/docs/reference/admin/java/reference/com/google/firebase/messaging/MulticastMessage)

## 1.8.0

  * Clean up. Remove dependencies and code that is no longer used.
  * Update dependencies:
    * Removed backports.entry-points-selectable (1.1.1)
    * Removed chardet (4.0.0)
    * Removed requests (2.25.1)
    * Removed urllib3 (1.26.7)
    * Updated idna (2.10 -> 3.3)
    * Updated pyparsing (3.0.6 -> 3.0.7)
    * Updated attrs (21.2.0 -> 21.4.0)
    * Updated charset-normalizer (2.0.9 -> 2.0.12)
    * Updated filelock (3.4.0 -> 3.4.1)
    * Updated click (8.0.3 -> 8.0.4)
    * Updated freezegun (1.1.0 -> 1.2.0)
    * Updated identify (2.4.0 -> 2.4.4)
    * Updated regex (2021.11.10 -> 2022.3.2)
    * Installed tomli (1.2.3)
    * Updated typed-ast (1.4.3 -> 1.5.2)
    * Updated typing-extensions (4.0.1 -> 4.1.1)
    * Updated virtualenv (20.10.0 -> 20.13.3)
    * Updated google-auth (2.1.0 -> 2.6.0)
    * Updated mypy (0.910 -> 0.931)

## 1.7.0

  * Make _get_access_token async

## 1.6.0

  * Add support of Python 3.10
  * Fix typos in README.md

## 1.5.0

  * Update dependencies

## 1.4.0

  * Added channel_id option to Android config ([spec](https://firebase.google.com/docs/reference/fcm/rest/v1/projects.messages#AndroidNotification))

## 1.3.5

  * [FIX] Adjust APS encoder in order to properly construct background push notification.

## 1.3.4

  * [FIX] Set properly attribute ``content-available`` for APNS payload. The attribute indicates that push
  notification should be considered [background](https://developer.apple.com/documentation/usernotifications/setting_up_a_remote_notification_server/pushing_background_updates_to_your_app).

## 1.3.3

  * [FIX] Use numeric representation for boolean attributes ``mutable-content`` and ``content-available``.

## 1.3.2

  * [FIX] Encode ``Aps`` message according to APNS [specification](https://developer.apple.com/documentation/usernotifications/setting_up_a_remote_notification_server/generating_a_remote_notification)
  * [FIX] Util ``cleanup_firebase_message`` to remove null values for dict object.
  * [CHORE] Update dependencies

## 1.3.1

  * [FIX] ``APNSPayload`` message no longer support attribute ``custom_data``

## 1.3.0

  * [FIX] APNS custom data properly incorporate into the push notification payload. So instead of passing ``custom_data``
  as-is into payload and by that introducing one more nested level, extract all the key from ``custom_data`` and
  put them on the same level as ``aps`` attribute.

## 1.2.1

  * Added verbosity when making request to Firebase

## 1.2.0

  * Added instrumentation to cleanup Firebase message before it can gets send. This is requirements that Firebase put on
  us, otherwise it fails with 400 error code, which basically says that payload is not well formed.

## 1.1.0

  * Update 3rd-party dependencies:
    - `google-auth = "~1.27.1"`
    - `httpx = "<1.0.0"`

## 1.0.0

  * Remastering main client.
    * method ``build_common_message`` completely dropped in favor of concept of message structures (module  ``messages``).

    * the signature of method ``push`` has changed. From now on, it expects to receive instances of ``messages.*`` for
      Android config and APNS config rather than raw data, which then has to be dynamically analyzed and mapped to the
      most appropriate message type.

    * static methods ``build_android_message`` and ``build_apns_message`` renamed to ``build_android_config`` and
      ``build_apns_config``.

    * static methods ``build_android_config`` and ``build_apns_config`` return ``messages.AndroidConfig`` and
      ``messages.APNSConfig`` respectively and aimed to simplify the process of creating configurations.

  * Introduce module ``messages`` the main aim is to simplify the process of constructing Push notification messages.
    The module houses the message structures that can be used to construct a push notification payload.

  * Fix CD workflow. Make step ``release`` dependent on ``create-virtualenv``.

  * Update ``README.md`` with more examples.

  * Every request to Firebase tagged with ``X-Request-Id``

## 0.4.0

  * Method ``push()`` no longer has parameter ``alert_text``. The parameter ``notification_body`` should be used
   instead.

## 0.3.0

  * Fix version

## 0.2.0

  * Update README.md

## 0.1.0

  * First release on PyPI.

# Changelog

## 3.0.0
Remastering client interface
* [BREAKING] The methods ``push`` and ``push_multicast`` renamed to ``send`` and ``send_multicast`` accordingly.
* [BREAKING] The signatures of the methods ``send`` and ``send_multicast`` have been changed.
  * Method ``push`` accepts instance of ``messages.Message`` and returns ``messages.FcmPushBatchResponse``
  * Method ``push_multicast`` accepts instance of ``messages.MulticastMessage`` and returns ``messages.FcmPushBatchResponse``
* New method ``send_all`` to send messages in a single batch has been added. It takes a list of ``messages.Message`` instances.
* ``README.md`` has been updated to highlight different in interfaces for versions prior **3.x** and after
* Error class ``FcmPushMulticastResponse`` renamed to ``FcmPushBatchResponse``.

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

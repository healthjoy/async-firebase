# Changelog

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

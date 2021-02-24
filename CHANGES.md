# Changelog

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

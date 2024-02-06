# async-firebase is a lightweight asynchronous client to interact with Firebase Cloud Messaging for sending push notification to Android and iOS devices

[![PyPI download month](https://img.shields.io/pypi/dm/async-firebase.svg)](https://pypi.python.org/pypi/async-firebase/)
[![PyPI version fury.io](https://badge.fury.io/py/async-firebase.svg)](https://pypi.python.org/pypi/async-firebase/)
[![PyPI license](https://img.shields.io/pypi/l/async-firebase.svg)](https://pypi.python.org/pypi/async-firebase/)
[![PyPI pyversions](https://img.shields.io/pypi/pyversions/async-firebase.svg)](https://pypi.python.org/pypi/async-firebase/)
[![CI](https://github.com/healthjoy/async-firebase/actions/workflows/ci.yml/badge.svg)](https://github.com/healthjoy/async-firebase/actions/workflows/ci.yml)
[![Codacy coverage](https://img.shields.io/codacy/coverage/b6a59cdf5ca64eab9104928d4f9bbb97?logo=codacy)](https://app.codacy.com/gh/healthjoy/async-firebase/dashboard)


  * Free software: MIT license
  * Requires: Python 3.8+

## Features

  * Extremely lightweight and does not rely on ``firebase-admin`` which is hefty
  * Send push notifications to Android and iOS devices
  * Send Multicast push notification to Android and iOS devices
  * Send Web push notifications
  * Set TTL (time to live) for notifications
  * Set priority for notifications
  * Set collapse-key for notifications
  * Dry-run mode for testing purpose

## Installation
To install `async-firebase`, simply execute the following command in a terminal:
```shell script
$ pip install async-firebase
```

## Getting started
### async-firebase < 3.0.0
To send push notification to Android:
```python3
import asyncio

from async_firebase import AsyncFirebaseClient


async def main():
    client = AsyncFirebaseClient()
    client.creds_from_service_account_file("secret-store/mobile-app-79225efac4bb.json")

    # or using dictionary object
    # client.creds_from_service_account_info({...}})

    device_token = "..."

    android_config = client.build_android_config(
        priority="high",
        ttl=2419200,
        collapse_key="push",
        data={"discount": "15%", "key_1": "value_1", "timestamp": "2021-02-24T12:00:15"},
        title="Store Changes",
        body="Recent store changes",
    )
    response = await client.push(device_token=device_token, android=android_config)

    print(response.success, response.message_id)

if __name__ == "__main__":
    asyncio.run(main())
```

To send push notification to iOS:

```python3
import asyncio

from async_firebase import AsyncFirebaseClient


async def main():
    client = AsyncFirebaseClient()
    client.creds_from_service_account_file("secret-store/mobile-app-79225efac4bb.json")

    # or using dictionary object
    # client.creds_from_service_account_info({...}})

    device_token = "..."

    apns_config = client.build_apns_config(
        priority="normal",
        ttl=2419200,
        apns_topic="store-updated",
        collapse_key="push",
        title="Store Changes",
        alert="Recent store changes",
        badge=1,
        category="test-category",
        custom_data={"discount": "15%", "key_1": "value_1", "timestamp": "2021-02-24T12:00:15"}
    )
    response = await client.push(device_token=device_token, apns=apns_config)

    print(response.success)

if __name__ == "__main__":
    asyncio.run(main())
```

This prints:

```shell script
"projects/mobile-app/messages/0:2367799010922733%7606eb557606ebff"
```

To manual construct message:
```python3
import asyncio
from datetime import datetime

from async_firebase.messages import APNSConfig, APNSPayload, ApsAlert, Aps
from async_firebase import AsyncFirebaseClient


async def main():
    apns_config = APNSConfig(**{
        "headers": {
            "apns-expiration": str(int(datetime.utcnow().timestamp()) + 7200),
            "apns-priority": "10",
            "apns-topic": "test-topic",
            "apns-collapse-id": "something",
        },
        "payload": APNSPayload(**{
            "aps": Aps(**{
                "alert": ApsAlert(title="some-title", body="alert-message"),
                "badge": 0,
                "sound": "default",
                "content_available": True,
                "category": "some-category",
                "mutable_content": False,
                "custom_data": {
                    "link": "https://link-to-somewhere.com",
                    "ticket_id": "YXZ-655512",
                },
            })
        })
    })

    device_token = "..."

    client = AsyncFirebaseClient()
    client.creds_from_service_account_info({...})
    response = await client.push(device_token=device_token, apns=apns_config)
    print(response.success)


if __name__ == "__main__":
    asyncio.run(main())
```

### async-firebase >= 3.0.0
To send push notification to Android:
```python3
import asyncio

from async_firebase import AsyncFirebaseClient
from async_firebase.messages import Message


async def main():
    client = AsyncFirebaseClient()
    client.creds_from_service_account_file("secret-store/mobile-app-79225efac4bb.json")

    # or using dictionary object
    # client.creds_from_service_account_info({...}})

    device_token: str = "..."

    android_config = client.build_android_config(
        priority="high",
        ttl=2419200,
        collapse_key="push",
        data={"discount": "15%", "key_1": "value_1", "timestamp": "2021-02-24T12:00:15"},
        title="Store Changes",
        body="Recent store changes",
    )
    message = Message(android=android_config, token=device_token)
    response = await client.send(message)

    print(response.success, response.message_id)

if __name__ == "__main__":
    asyncio.run(main())
```

To send push notification to iOS:

```python3
import asyncio

from async_firebase import AsyncFirebaseClient
from async_firebase.messages import Message


async def main():
    client = AsyncFirebaseClient()
    client.creds_from_service_account_file("secret-store/mobile-app-79225efac4bb.json")

    # or using dictionary object
    # client.creds_from_service_account_info({...}})

    device_token: str = "..."

    apns_config = client.build_apns_config(
        priority="normal",
        ttl=2419200,
        apns_topic="store-updated",
        collapse_key="push",
        title="Store Changes",
        alert="Recent store changes",
        badge=1,
        category="test-category",
        custom_data={"discount": "15%", "key_1": "value_1", "timestamp": "2021-02-24T12:00:15"}
    )
    message = Message(apns=apns_config, token=device_token)
    response = await client.send(message)

    print(response.success)

if __name__ == "__main__":
    asyncio.run(main())
```

This prints:

```shell script
"projects/mobile-app/messages/0:2367799010922733%7606eb557606ebff"
```

To manual construct message:
```python3
import asyncio
from datetime import datetime

from async_firebase.messages import APNSConfig, APNSPayload, ApsAlert, Aps, Message
from async_firebase import AsyncFirebaseClient


async def main():
    apns_config = APNSConfig(**{
        "headers": {
            "apns-expiration": str(int(datetime.utcnow().timestamp()) + 7200),
            "apns-priority": "10",
            "apns-topic": "test-topic",
            "apns-collapse-id": "something",
        },
        "payload": APNSPayload(**{
            "aps": Aps(**{
                "alert": ApsAlert(title="some-title", body="alert-message"),
                "badge": 0,
                "sound": "default",
                "content_available": True,
                "category": "some-category",
                "mutable_content": False,
                "custom_data": {
                    "link": "https://link-to-somewhere.com",
                    "ticket_id": "YXZ-655512",
                },
            })
        })
    })

    device_token: str = "..."

    client = AsyncFirebaseClient()
    client.creds_from_service_account_info({...})
    message = Message(apns=apns_config, token=device_token)
    response = await client.send(message)
    print(response.success)


if __name__ == "__main__":
    asyncio.run(main())
```

## License

``async-firebase`` is offered under the MIT license.

## Source code

The latest developer version is available in a GitHub repository:
[https://github.com/healthjoy/async-firebase](https://github.com/healthjoy/async-firebase)

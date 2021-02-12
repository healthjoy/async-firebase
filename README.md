# Async Firebase Cloud Messaging client

[![PyPI download total](https://img.shields.io/pypi/dt/async-firebase.svg)](https://pypi.python.org/pypi/async-firebase/)
[![PyPI download month](https://img.shields.io/pypi/dm/async-firebase.svg)](https://pypi.python.org/pypi/async-firebase/)
[![PyPI version fury.io](https://badge.fury.io/py/async-firebase.svg)](https://pypi.python.org/pypi/async-firebase/)
[![PyPI license](https://img.shields.io/pypi/l/async-firebase.svg)](https://pypi.python.org/pypi/async-firebase/)
[![PyPI pyversions](https://img.shields.io/pypi/pyversions/async-firebase.svg)](https://pypi.python.org/pypi/async-firebase/)
[![GitHub Workflow Status for CI](https://img.shields.io/github/workflow/status/healthjoy/async-firebase/CI?label=CI&logo=github)](https://github.com/healthjoy/async-firebase/actions?query=workflow%3ACI)
[![Codacy coverage](https://img.shields.io/codacy/coverage/b6a59cdf5ca64eab9104928d4f9bbb97?logo=codacy)](https://app.codacy.com/gh/healthjoy/async-firebase/dashboard)

Async Firebase - is a lightweight asynchronous client to interact with Firebase.

  * Free software: MIT license
  * Requires: Python 3.6+

## Features
 TBD...

## Installation
```shell script
$ pip install async-firebase
```

## Getting started
To send push notification to either Android or iOS device:
```python3
import asyncio

from async_firebase import AsyncFirebaseClient


async def main():
    client = AsyncFirebaseClient()
    client.creds_from_service_account_file("secret-store/mobile-app-79225efac4bb.json")

    device_token = "..."

    response = await client.push(
        device_token=device_token,
        notification_title="Store Changes",
        notification_body="Recent store changes",
        notification_data={
            "discount": "15%",
            "key_1": "value_1"
        },
        priority="normal",
        apns_topic="store-updates",
        collapse_key="push",
        alert_text="test-alert",
        category="test-category",
        badge=1,
    )

    print(response)

if __name__ == "__main__":
    asyncio.run(main())
```

This prints:
```shell script
{"name": "projects/mobile-app/messages/0:2367799010922733%7606eb557606ebff"}
```

## License

``async-firebase`` is offered under the MIT license.

## Source code

The latest developer version is available in a GitHub repository:
https://github.com/healthjoy/async-firebase

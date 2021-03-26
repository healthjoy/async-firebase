import asyncio
import inspect
import time
import sys
import threading
from concurrent.futures.thread import ThreadPoolExecutor

import pytest

from async_firebase.messages import (
    AndroidConfig,
    AndroidNotification,
    APNSConfig,
    APNSPayload,
    Aps,
    ApsAlert,
    Message,
    Notification,
    PushNotification,
)
from async_firebase.utils import cleanup_firebase_message, make_async, remove_null_values


pytestmark = pytest.mark.asyncio


@pytest.mark.parametrize(
    "data, exp_result", (
        ({
            "android": {},
            "apns": {},
            "condition": None,
            "data": {},
            "notification": {},
            "token": None,
            "topic": None,
            "webpush": None,
        }, {}),
        ({"key_1": None, "key_2": "value_2", "key_3": []}, {"key_2": "value_2"}),
        ({
            "falsy_string": "",
            "falsy_int": 0,
            "falsy_bool": False,
            "falsy_float": 0.0,
            "falsy_dict": {},
            "falsy_list": [],
        }, {"falsy_string": "", "falsy_int": 0, "falsy_bool": False, "falsy_float": 0.0}),
        ({}, {}),
        ({
            "key_1": {
                "sub_key_1": {},
                "sub_key_2": None,
                "sub_key_3": [],
            },
            "key_2": None
         }, {"key_1": {"sub_key_1": {}, "sub_key_2": None, "sub_key_3": []}})
    )
)
def test_remove_null_values(data, exp_result):
    result = remove_null_values(data)
    assert result == exp_result


def test_make_async_ensure_coroutine_function():

    @make_async
    def func1():
        return True

    assert inspect.iscoroutinefunction(func1)


async def test_make_async_get_result():

    @make_async
    def sync_func(seconds_to_block, event):
        for i in range(seconds_to_block):
            if event.is_set():
                return
            print("blocking {}/{}".format(i, seconds_to_block))
            time.sleep(1)
        print("done blocking {}".format(seconds_to_block))

    async def count_sum(x, y):
        return x + y

    async def count_mul(x, y):
        return x * y

    event = threading.Event()
    done, pending = await asyncio.wait(
        [sync_func(100, event), count_sum(5, 5), count_mul(5, 5)],
        return_when=asyncio.FIRST_COMPLETED
    )
    assert done
    assert len(pending) == 1
    sleeping_task = pending.pop()
    assert not sleeping_task.done()
    sleeping_task.cancel()
    event.set()
    try:
        await asyncio.gather(sleeping_task)
    except asyncio.CancelledError:
        pass
    assert sleeping_task.cancelled()


async def test_make_async_pre_created_loop():

    @make_async
    def func1(loop=None):
        return

    pre_created_loop = asyncio.get_event_loop()
    pre_created_loop.create_task(func1(loop=pre_created_loop))

    is_python36 = sys.version_info < (3, 7)
    if is_python36:
        all_tasks = asyncio.tasks.Task.all_tasks()
        current_task = asyncio.tasks.Task.current_task()
    else:
        all_tasks = asyncio.all_tasks()
        current_task = asyncio.current_task()

    for task in all_tasks:
        if task == current_task:
            continue
        if is_python36:
            assert id(task._loop) == id(pre_created_loop)
        else:
            assert id(task.get_loop()) == id(pre_created_loop)


async def test_make_async_pre_created_thread_pool_executor():

    @make_async
    def func1(executor=None):
        return threading.get_ident()

    thread_pool_executor = ThreadPoolExecutor(1)
    thread_id = await func1(executor=thread_pool_executor)

    thread = thread_pool_executor._threads.copy().pop()
    assert thread.ident == thread_id
    thread_pool_executor.shutdown(wait=True)


@pytest.mark.parametrize(
    "firebase_message, exp_result", (
        (
            AndroidNotification(title="push-title", body="push-body"),
            {"title": "push-title", "body": "push-body"}
        ),
        (
            AndroidConfig(collapse_key="group", priority="normal", ttl="3600s"),
            {"collapse_key": "group", "priority": "normal", "ttl": "3600s"}
        ),
        (
            ApsAlert(title="push-title", body="push-body"), {"title": "push-title", "body": "push-body"}
        ),
        (
            Aps(alert="alert", badge=9), {"alert": "alert", "badge": 9}
        ),
        (
            APNSPayload(aps=Aps(alert="push-text", custom_data={"foo": "bar"})),
            {"aps": {"alert": "push-text", "custom_data": {"foo": "bar"}}}
        ),
        (
            APNSConfig(headers={"x-header": "x-data"}), {"headers": {"x-header": "x-data"}}
        ),
        (
            Notification(title="push-title", body="push-body"), {"title": "push-title", "body": "push-body"}
        ),
        (
            Message(
                token="qwerty",
                notification=Notification(title="push-title", body="push-body"),
                apns=APNSConfig(
                    headers={"hdr": "qwe"},
                    payload=APNSPayload(
                        aps=Aps(
                            sound="generic",
                        ),
                    )
                )
            ),
            {
                "token": "qwerty",
                "notification": {"title": "push-title", "body": "push-body"},
                "apns": {
                    "headers": {"hdr": "qwe"},
                    "payload": {
                        "aps": {"sound": "generic"}
                    }
                }
            }
        ),
        (
            PushNotification(
                message=Message(
                    token="secret-token",
                    notification=Notification(title="push-title", body="push-body"),
                    android=AndroidConfig(
                        collapse_key="group",
                        notification=AndroidNotification(
                            title="android-push-title",
                            body="android-push-body"
                        )
                    )
                )
            ),
            {
                "message": {
                    "token": "secret-token",
                    "notification": {"title": "push-title", "body": "push-body"},
                    "android": {
                        "collapse_key": "group",
                        "notification": {"title": "android-push-title", "body": "android-push-body"}
                    }
                },
                "validate_only": False
            },
        ),
    )
)
def test_cleanup_firebase_message(firebase_message, exp_result):
    result = cleanup_firebase_message(firebase_message)
    assert result == exp_result

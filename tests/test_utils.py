import asyncio
import inspect
import time
import threading

import pytest

from async_firebase.utils import make_async, remove_null_values


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
            print('blocking {}/{}'.format(i, seconds_to_block))
            time.sleep(1)
        print('done blocking {}'.format(seconds_to_block))

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

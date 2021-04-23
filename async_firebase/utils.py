import asyncio
import typing as t
from concurrent.futures.thread import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import fields, is_dataclass
from functools import partial, wraps


def make_async(func: t.Callable):
    @wraps(func)
    async def run(
        *args,
        loop: t.Optional[asyncio.AbstractEventLoop] = None,
        executor: t.Optional[ThreadPoolExecutor] = None,
        **kwargs
    ):
        if loop is None:
            loop = asyncio.get_event_loop()
        sync_func = partial(func, *args, **kwargs)
        if executor is None:
            with ThreadPoolExecutor() as executor:  # pylint: disable=redefined-argument-from-local)
                return await loop.run_in_executor(executor, sync_func)
        return await loop.run_in_executor(executor, sync_func)

    return run


def remove_null_values(dict_value: t.Dict[str, t.Any]) -> t.Dict[str, t.Any]:
    """Remove Falsy values from the dictionary."""
    return {k: v for k, v in dict_value.items() if v not in [None, [], {}]}


def cleanup_firebase_message(dataclass_obj, dict_factory: t.Callable = dict) -> dict:
    """
    The instrumentation to cleanup firebase message from null values.

    Example::

        considering following dataclass

        msg = Message(
            token='qwe',
            data={},
            notification=Notification(title='push-title', body='push-body'),
            android=None,
            webpush={},
            apns=APNSConfig(
                headers={'hdr': 'qwe'},
                payload=APNSPayload(
                    aps=Aps(
                        alert=None,
                        badge=None,
                        sound='generic',
                        content_available=None,
                        category=None,
                        thread_id=None,
                        mutable_content=None,
                        custom_data={}
                    ),
                    custom_data={}
                )
            ),
            topic=None,
            condition=None
        )

        >>> dataclass_to_dict_remove_null_values(msg)
        {
            'token': 'qwe',
            'notification': {'title': 'push-title', 'body': 'push-body'},
            'apns': {
                'headers': {'hdr': 'qwe'},
                'payload': {
                    'aps': {'sound': 'generic'}
                }
            }
        }

    :param dataclass_obj: instance of dataclass. This suppose to be instance of ``messages.PushNotification`` or
        ``messages.Message``.
    :param dict_factory: if given, ``dict_factory`` will be used instead of built-in dict.
        The function applies recursively to field values that are dataclass instances.
    :return: the fields of a dataclass instance as a new dictionary mapping field names to field values.
    """
    if is_dataclass(dataclass_obj):
        result = []
        for f in fields(dataclass_obj):
            value = cleanup_firebase_message(getattr(dataclass_obj, f.name), dict_factory)
            result.append((f.name, value))
        return remove_null_values(dict_factory(result))
    elif isinstance(dataclass_obj, (list, tuple)):
        return type(dataclass_obj)(cleanup_firebase_message(v, dict_factory) for v in dataclass_obj)  # type: ignore
    elif isinstance(dataclass_obj, dict):
        return remove_null_values({k: cleanup_firebase_message(v, dict_factory) for k, v in dataclass_obj.items()})
    return deepcopy(dataclass_obj)

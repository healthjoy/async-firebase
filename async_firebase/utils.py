import asyncio
import typing as t
from concurrent.futures.thread import ThreadPoolExecutor
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

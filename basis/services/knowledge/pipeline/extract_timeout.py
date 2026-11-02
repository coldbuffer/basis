"""Wall-clock timeout for synchronous semantica extraction (X-04)."""

from __future__ import annotations

import concurrent.futures
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T")


class ExtractionTimeoutError(Exception):
    def __init__(self, timeout_seconds: float) -> None:
        self.timeout_seconds = timeout_seconds
        self.message = f"知识抽取超过 {int(timeout_seconds)} 秒限制"
        super().__init__(self.message)


def run_sync_with_timeout(fn: Callable[[], T], timeout_seconds: float) -> T:
    if timeout_seconds <= 0:
        return fn()
    pool = concurrent.futures.ThreadPoolExecutor(max_workers=1)
    future = pool.submit(fn)
    try:
        result = future.result(timeout=timeout_seconds)
    except concurrent.futures.TimeoutError:
        future.cancel()
        # Do not wait for in-flight semantica work; the thread may run until process exit.
        pool.shutdown(wait=False, cancel_futures=True)
        raise ExtractionTimeoutError(timeout_seconds) from None
    pool.shutdown(wait=True)
    return result

#!/usr/bin/env python3
# Copyright (c) 2022-2023 Sandor Balazsi (sandor.balazsi@gmail.com)
# vim: ts=4:sw=4:sts=4:et

import time, datetime, logging
from functools import wraps

LOGGER = logging.getLogger(__name__)

def debug(msg, runtime=False):
    def decorator(func, *args, **kwargs):
        @wraps(func)
        def wrapper(*args, **kwargs):
            start = time.monotonic()
            result = func(*args, **kwargs)
            delta = datetime.timedelta(seconds=time.monotonic() - start)
            duration = ' (duration: {})'.format(delta) if runtime else ''
            if not callable(msg):
                LOGGER.debug(msg + duration)
            elif result != None:
                LOGGER.debug(msg(result) + duration)
            return result
        return wrapper
    return decorator

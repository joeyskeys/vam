# -*- coding: utf-8 -*-

import functools

def singleton(cls):
    """Make a class a Singleton class (only one instance)"""
    instances = {}

    @functools.wraps(cls)
    def wrapper_singleton(*args, **kwargs):
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]

    return wrapper_singleton
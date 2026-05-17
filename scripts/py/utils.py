# -*- coding: utf-8 -*-

import functools
from typing import Dict, List

import maya.api.OpenMaya as om
import maya.cmds as cmds

def singleton(cls):
    """Make a class a Singleton class (only one instance)"""
    instances = {}

    @functools.wraps(cls)
    def wrapper_singleton(*args, **kwargs):
        if cls not in instances:
            instances[cls] = cls(*args, **kwargs)
        return instances[cls]

    return wrapper_singleton


def object_pivots_world(paths: List[str]) -> Dict[str, om.MVector]:
    """Return per-object bbox center pivots in world space."""
    out: Dict[str, om.MVector] = {}
    for path in paths:
        bb = cmds.exactWorldBoundingBox(path)
        out[path] = om.MVector(
            (float(bb[0]) + float(bb[3])) * 0.5,
            (float(bb[1]) + float(bb[4])) * 0.5,
            (float(bb[2]) + float(bb[5])) * 0.5,
        )
    return out
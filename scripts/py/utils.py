# -*- coding: utf-8 -*-

import functools
from typing import Dict, List, Optional, Tuple

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


def local_axes_world(pivot_path: Optional[str]) -> Tuple[om.MVector, om.MVector, om.MVector]:
    """Return local X/Y/Z axes in world space for a transform path."""
    if not pivot_path:
        return (
            om.MVector(1, 0, 0),
            om.MVector(0, 1, 0),
            om.MVector(0, 0, 1),
        )

    sel = om.MSelectionList()
    sel.add(pivot_path)
    dag = sel.getDagPath(0)
    m = dag.inclusiveMatrix()

    # Keep extraction consistent with row-vector matrix usage in this project.
    lx = om.MVector(m.getElement(0, 0), m.getElement(0, 1), m.getElement(0, 2)).normalize()
    ly = om.MVector(m.getElement(1, 0), m.getElement(1, 1), m.getElement(1, 2)).normalize()
    lz = om.MVector(m.getElement(2, 0), m.getElement(2, 1), m.getElement(2, 2)).normalize()
    return lx, ly, lz
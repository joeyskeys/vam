# -*- coding: utf-8 -*-
"""
Modal viewport scaling: enter on scale state, move tracks mouse via
MPxContext.doMotion (and doHold fallback), press confirms.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

import maya.api.OpenMaya as om
import maya.api.OpenMayaUI as omui
import maya.cmds as cmds
from utils import object_pivots_world


def _event_viewport_xy(event: Any) -> Tuple[float, float]:
    """Mouse position for drag deltas (viewport-style coordinates)."""
    try:
        return event.position(om.MSpace.kScreen)
    except Exception:
        pass
    try:
        return event.position(omui.MSpace.kScreen)
    except Exception:
        pass
    try:
        pos = event.position
        if isinstance(pos, (tuple, list)) and len(pos) >= 2:
            return float(pos[0]), float(pos[1])
    except Exception:
        pass
    return 0.0, 0.0


def _camera_view_frame(cam_path: om.MDagPath) -> Tuple[om.MVector, om.MVector]:
    """Camera right/up vectors in world space."""
    m = cam_path.inclusiveMatrix()
    right = om.MVector(m[0], m[1], m[2]).normalize()
    up = om.MVector(m[4], m[5], m[6]).normalize()
    return right, up


def _world_units_per_pixel(pivot: om.MVector, eye: om.MVector, cam_path: om.MDagPath,
                           port_w: float, port_h: float) -> Tuple[float, float]:
    """Approximate world translation per pixel at ``pivot`` depth."""
    fn = om.MFnCamera(cam_path)
    if fn.isOrtho():
        ow = float(fn.orthoWidth())
        s = ow / max(port_w, 1.0)
        return s, s

    vfov = float(fn.verticalFieldOfView())
    dist = (pivot - eye).length()
    if dist < 1.0e-4:
        dist = 1.0e-4
    half_h = dist * math.tan(vfov * 0.5)
    sy = (2.0 * half_h) / max(port_h, 1.0)
    sx = sy * (port_w / max(port_h, 1.0))
    return sx, sy


def _selection_pivot(paths: List[str]) -> om.MVector:
    """Bounding-box center of selection in world space."""
    if not paths:
        return om.MVector(0, 0, 0)
    bb = cmds.exactWorldBoundingBox(paths)
    return om.MVector(
        (float(bb[0]) + float(bb[3])) * 0.5,
        (float(bb[1]) + float(bb[4])) * 0.5,
        (float(bb[2]) + float(bb[5])) * 0.5,
    )


def _selection_ref_len(paths: List[str]) -> float:
    """Diagonal length of selection bbox used to normalize scale sensitivity."""
    if not paths:
        return 1.0
    bb = cmds.exactWorldBoundingBox(paths)
    dx = float(bb[3]) - float(bb[0])
    dy = float(bb[4]) - float(bb[1])
    dz = float(bb[5]) - float(bb[2])
    diag = (dx * dx + dy * dy + dz * dz) ** 0.5
    return max(diag, 1.0e-3)


def _local_axes_world(pivot_path: Optional[str]) -> Tuple[om.MVector, om.MVector, om.MVector]:
    """Pivot object's local X/Y/Z as unit vectors in world space."""
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
    lx = om.MVector(m.getElement(0, 0), m.getElement(1, 0), m.getElement(2, 0)).normalize()
    ly = om.MVector(m.getElement(0, 1), m.getElement(1, 1), m.getElement(2, 1)).normalize()
    lz = om.MVector(m.getElement(0, 2), m.getElement(1, 2), m.getElement(2, 2)).normalize()
    return lx, ly, lz


def _world_matrix(path: str) -> om.MMatrix:
    return om.MMatrix(cmds.xform(path, query=True, matrix=True, worldSpace=True))


def _matrix_to_list(m: om.MMatrix) -> List[float]:
    return [float(m.getElement(r, c)) for r in range(4) for c in range(4)]


def _translation_matrix(v: om.MVector) -> om.MMatrix:
    return om.MMatrix((
        1.0, 0.0, 0.0, 0.0,
        0.0, 1.0, 0.0, 0.0,
        0.0, 0.0, 1.0, 0.0,
        float(v.x), float(v.y), float(v.z), 1.0,
    ))


def _uniform_scale_matrix(factor: float) -> om.MMatrix:
    return om.MMatrix((
        factor, 0.0, 0.0, 0.0,
        0.0, factor, 0.0, 0.0,
        0.0, 0.0, factor, 0.0,
        0.0, 0.0, 0.0, 1.0,
    ))


def _axis_scale_matrix(direction: om.MVector, factor: float) -> om.MMatrix:
    """World-space scale matrix along one axis direction."""
    u = om.MVector(direction)
    if u.length() < 1.0e-8:
        return _uniform_scale_matrix(1.0)
    u.normalize()
    x, y, z = float(u.x), float(u.y), float(u.z)
    k = factor - 1.0
    return om.MMatrix((
        1.0 + k * x * x, k * x * y,       k * x * z,       0.0,
        k * y * x,       1.0 + k * y * y, k * y * z,       0.0,
        k * z * x,       k * z * y,       1.0 + k * z * z, 0.0,
        0.0,             0.0,             0.0,             1.0,
    ))


def _clamp_factor(factor: float) -> float:
    return max(0.01, min(100.0, factor))


def _axis_direction_for_base(axis: str, base: str, pivot_path: Optional[str]) -> Optional[om.MVector]:
    if axis not in ('x', 'y', 'z'):
        return None
    idx = {'x': 0, 'y': 1, 'z': 2}[axis]
    if base == 'local':
        return _local_axes_world(pivot_path)[idx]
    return (
        om.MVector(1, 0, 0),
        om.MVector(0, 1, 0),
        om.MVector(0, 0, 1),
    )[idx]


def scale_modal_begin(axis: str, base: str) -> Optional[Dict[str, Any]]:
    """Begin modal scaling when entering scale state."""
    transforms = cmds.ls(selection=True, type='transform', long=True)
    if not transforms:
        print("[VAM scale] scale_modal_begin: abort — no transform in selection")
        return None

    view = omui.M3dView.active3dView()
    if view is None or not view.isVisible():
        print("[VAM scale] scale_modal_begin: abort — active3dView missing or not visible")
        return None

    port_w = float(view.portWidth())
    port_h = float(view.portHeight())
    if port_w < 1.0 or port_h < 1.0:
        print(f"[VAM scale] scale_modal_begin: abort — bad viewport size {port_w}x{port_h}")
        return None

    cam_path = view.getCamera()
    eye = om.MVector(cam_path.inclusiveMatrix()[12], cam_path.inclusiveMatrix()[13], cam_path.inclusiveMatrix()[14])
    view_right, view_up = _camera_view_frame(cam_path)
    pivot_pt = _selection_pivot(transforms)
    sx, sy = _world_units_per_pixel(pivot_pt, eye, cam_path, port_w, port_h)

    session = {
        'axis': axis,
        'base': base,
        'start_mx': None,
        'start_my': None,
        'sx': sx,
        'sy': sy,
        'view_right': view_right,
        'view_up': view_up,
        'pivot_path': transforms[-1],
        'pivot_pt': pivot_pt,
        'object_pivots': object_pivots_world(transforms),
        'ref_len': _selection_ref_len(transforms),
        'initial_world_m': {p: _world_matrix(p) for p in transforms},
        'paths': transforms,
    }
    return session


def scale_modal_update(session: Dict[str, Any], event: Any) -> None:
    """Apply scaling from modal origin to current mouse (origin fixed after first sample)."""
    mx, my = _event_viewport_xy(event)
    if session['start_mx'] is None:
        session['start_mx'] = mx
        session['start_my'] = my
        return

    dx = mx - session['start_mx']
    dy = my - session['start_my']

    ref_len = max(float(session['ref_len']), 1.0e-3)
    base = session.get('base', 'screen')
    axis = session.get('axis', 'none')

    sensitivity = 2.0

    if base == 'screen' or axis == 'none':
        signed = (-dy) * session['sy']
        factor = _clamp_factor(1.0 + sensitivity * (signed / ref_len))
        scale_m = _uniform_scale_matrix(factor)
    else:
        direction = _axis_direction_for_base(axis, base, session.get('pivot_path'))
        if direction is None:
            signed = (-dy) * session['sy']
            factor = _clamp_factor(1.0 + sensitivity * (signed / ref_len))
            scale_m = _uniform_scale_matrix(factor)
        else:
            raw = (
                session['view_right'] * (dx * session['sx']) +
                session['view_up'] * (dy * session['sy'])
            )
            signed = raw * direction
            factor = _clamp_factor(1.0 + sensitivity * (signed / ref_len))
            scale_m = _axis_scale_matrix(direction, factor)

    for path in session['paths']:
        pivot = session['object_pivots'].get(path, session['pivot_pt'])
        pivot_m = _translation_matrix(pivot)
        pivot_inv_m = _translation_matrix(-pivot)
        delta_m = pivot_inv_m * scale_m * pivot_m
        initial_m = session['initial_world_m'][path]
        new_m = initial_m * delta_m
        cmds.xform(path, matrix=_matrix_to_list(new_m), worldSpace=True)


def scale_modal_restore(session: Dict[str, Any]) -> None:
    """Restore world matrices captured at modal begin (cancel)."""
    for path, m0 in session['initial_world_m'].items():
        cmds.xform(path, matrix=_matrix_to_list(m0), worldSpace=True)

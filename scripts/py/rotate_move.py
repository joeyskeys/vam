# -*- coding: utf-8 -*-
"""
Modal viewport rotation: enter on rotate state, move tracks mouse via
MPxContext.doMotion (and doHold fallback), press confirms.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

import maya.api.OpenMaya as om
import maya.api.OpenMayaUI as omui
import maya.cmds as cmds
from utils import local_axes_world, object_pivots_world


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


def _camera_view_frame(cam_path: om.MDagPath) -> Tuple[om.MVector, om.MVector, om.MVector]:
    """Camera right/up/forward vectors in world space."""
    m = cam_path.inclusiveMatrix()
    right = om.MVector(m[0], m[1], m[2]).normalize()
    up = om.MVector(m[4], m[5], m[6]).normalize()
    local_z = om.MVector(m[8], m[9], m[10]).normalize()
    forward = (-local_z).normalize()
    return right, up, forward


def _world_to_view_xy(view: omui.M3dView, p: om.MVector) -> Optional[Tuple[float, float]]:
    """Project world point to viewport pixel coordinates."""
    try:
        x, y, _clipped = view.worldToView(om.MPoint(p.x, p.y, p.z))
        return float(x), float(y)
    except Exception:
        return None


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


def _axis_direction_for_base(
    axis: str,
    base: str,
    pivot_path: Optional[str],
    local_axes_start: Optional[Tuple[om.MVector, om.MVector, om.MVector]] = None,
) -> Optional[om.MVector]:
    if axis not in ('x', 'y', 'z'):
        return None
    idx = {'x': 0, 'y': 1, 'z': 2}[axis]
    if base == 'local':
        if local_axes_start is not None:
            return local_axes_start[idx]
        return local_axes_world(pivot_path)[idx]
    return (
        om.MVector(1, 0, 0),
        om.MVector(0, 1, 0),
        om.MVector(0, 0, 1),
    )[idx]


def _rotation_matrix(axis: om.MVector, angle_rad: float) -> om.MMatrix:
    """World-space rotation matrix around axis direction."""
    a = om.MVector(axis)
    if a.length() < 1.0e-8:
        return om.MMatrix.kIdentity
    a.normalize()
    q = om.MQuaternion(angle_rad, a)
    return q.asMatrix()


def _signed_mouse_orbit_delta(pivot_x: float, pivot_y: float,
                              prev_x: float, prev_y: float,
                              cur_x: float, cur_y: float) -> float:
    """
    Incremental signed orbit angle (radians) from previous to current mouse vector.

    Uses normalized direction vectors around pivot, so angle is independent of
    cursor radius (distance from object on screen).
    """
    px = prev_x - pivot_x
    py = prev_y - pivot_y
    cx = cur_x - pivot_x
    cy = cur_y - pivot_y

    lp = (px * px + py * py) ** 0.5
    lc = (cx * cx + cy * cy) ** 0.5
    if lp < 1.0e-5 or lc < 1.0e-5:
        return 0.0

    px /= lp
    py /= lp
    cx /= lc
    cy /= lc

    cross = px * cy - py * cx
    dot = max(-1.0, min(1.0, px * cx + py * cy))
    return -math.atan2(cross, dot)


def rotate_modal_begin(axis: str, base: str) -> Optional[Dict[str, Any]]:
    """Begin modal rotation when entering rotate state."""
    transforms = cmds.ls(selection=True, type='transform', long=True)
    if not transforms:
        print("[VAM rotate] rotate_modal_begin: abort — no transform in selection")
        return None

    view = omui.M3dView.active3dView()
    if view is None or not view.isVisible():
        print("[VAM rotate] rotate_modal_begin: abort — active3dView missing or not visible")
        return None

    cam_path = view.getCamera()
    view_right, view_up, view_forward = _camera_view_frame(cam_path)
    pivot_pt = _selection_pivot(transforms)
    pivot_screen = _world_to_view_xy(view, pivot_pt)

    session = {
        'axis': axis,
        'base': base,
        'start_mx': None,
        'start_my': None,
        'orbit_prev_mx': None,
        'orbit_prev_my': None,
        'orbit_angle_accum': 0.0,
        'view_right': view_right,
        'view_up': view_up,
        'view_forward': view_forward,
        'pivot_path': transforms[-1],
        'local_axes_start': local_axes_world(transforms[-1]),
        'pivot_pt': pivot_pt,
        'pivot_screen': pivot_screen,
        'object_pivots': object_pivots_world(transforms),
        'initial_world_m': {p: _world_matrix(p) for p in transforms},
        'paths': transforms,
    }
    return session


def rotate_modal_update(session: Dict[str, Any], event: Any) -> None:
    """Apply rotation from modal origin to current mouse (origin fixed after first sample)."""
    mx, my = _event_viewport_xy(event)
    if session['start_mx'] is None:
        session['start_mx'] = mx
        session['start_my'] = my
        session['orbit_prev_mx'] = mx
        session['orbit_prev_my'] = my
        session['orbit_angle_accum'] = 0.0
        return

    base = session.get('base', 'screen')
    axis = session.get('axis', 'none')
    dx = mx - session['start_mx']
    dy = my - session['start_my']
    view_forward = session['view_forward']
    view = omui.M3dView.active3dView()
    if view is not None and view.isVisible():
        try:
            _view_right, _view_up, view_forward = _camera_view_frame(view.getCamera())
            session['view_forward'] = view_forward
        except Exception:
            pass
    pivot_screen = session.get('pivot_screen')

    # Keep pivot projection in sync if camera changes mid-modal.
    if view is not None and view.isVisible():
        projected = _world_to_view_xy(view, session['pivot_pt'])
        if projected is not None:
            pivot_screen = projected
            session['pivot_screen'] = projected
    elif pivot_screen is None:
        pivot_screen = _world_to_view_xy(view, session['pivot_pt']) if view else None
        session['pivot_screen'] = pivot_screen

    if base == 'screen' or axis == 'none':
        rotate_axis = view_forward
        is_axis_constrained = False
    else:
        rotate_axis = _axis_direction_for_base(
            axis,
            base,
            session.get('pivot_path'),
            session.get('local_axes_start'),
        )
        if rotate_axis is None:
            rotate_axis = view_forward
            is_axis_constrained = False
        else:
            is_axis_constrained = True

    if pivot_screen is None:
        angle = (dx - dy) * 0.0045
    else:
        px, py = pivot_screen
        prev_mx = session.get('orbit_prev_mx')
        prev_my = session.get('orbit_prev_my')
        if prev_mx is None or prev_my is None:
            prev_mx = session['start_mx']
            prev_my = session['start_my']

        delta_angle = _signed_mouse_orbit_delta(
            px, py,
            prev_mx, prev_my,
            mx, my,
        )

        accum_angle = float(session.get('orbit_angle_accum', 0.0)) + delta_angle
        session['orbit_prev_mx'] = mx
        session['orbit_prev_my'] = my
        session['orbit_angle_accum'] = accum_angle
        angle = accum_angle

    if is_axis_constrained:
        angle = -angle

    rot_m = _rotation_matrix(rotate_axis, angle)

    for path in session['paths']:
        pivot = session['object_pivots'].get(path, session['pivot_pt'])
        pivot_m = _translation_matrix(pivot)
        pivot_inv_m = _translation_matrix(-pivot)
        delta_m = pivot_inv_m * rot_m * pivot_m
        initial_m = session['initial_world_m'][path]
        new_m = initial_m * delta_m
        cmds.xform(path, matrix=_matrix_to_list(new_m), worldSpace=True)


def rotate_modal_restore(session: Dict[str, Any]) -> None:
    """Restore world matrices captured at modal begin (cancel)."""
    for path, m0 in session['initial_world_m'].items():
        cmds.xform(path, matrix=_matrix_to_list(m0), worldSpace=True)

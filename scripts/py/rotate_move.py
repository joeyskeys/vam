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


def _rotation_matrix(axis: om.MVector, angle_rad: float) -> om.MMatrix:
    """World-space rotation matrix around axis direction."""
    a = om.MVector(axis)
    if a.length() < 1.0e-8:
        return om.MMatrix.kIdentity
    a.normalize()
    q = om.MQuaternion(angle_rad, a)
    return q.asMatrix()


def _signed_mouse_orbit_angle(pivot_x: float, pivot_y: float,
                              start_x: float, start_y: float,
                              cur_x: float, cur_y: float) -> float:
    """
    Signed angle (radians) between start and current mouse vectors around pivot.

    This gives Blender-like "rotate by orbiting around the object center" behavior.
    """
    sx = start_x - pivot_x
    sy = start_y - pivot_y
    cx = cur_x - pivot_x
    cy = cur_y - pivot_y
    ls = (sx * sx + sy * sy) ** 0.5
    lc = (cx * cx + cy * cy) ** 0.5
    if ls < 1.0e-5 or lc < 1.0e-5:
        return 0.0

    sx /= ls
    sy /= ls
    cx /= lc
    cy /= lc

    cross = sx * cy - sy * cx
    dot = max(-1.0, min(1.0, sx * cx + sy * cy))
    # Viewport pixel Y is typically down-positive, so flip sign to keep drag
    # direction intuitive for circular mouse motion around pivot.
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
        'view_right': view_right,
        'view_up': view_up,
        'view_forward': view_forward,
        'pivot_path': transforms[-1],
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
        return

    base = session.get('base', 'screen')
    axis = session.get('axis', 'none')
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
        rotate_axis = _axis_direction_for_base(axis, base, session.get('pivot_path'))
        if rotate_axis is None:
            rotate_axis = view_forward
            is_axis_constrained = False
        else:
            is_axis_constrained = True

    if pivot_screen is None:
        dx = mx - session['start_mx']
        dy = my - session['start_my']
        angle = (dx - dy) * 0.0045
    else:
        px, py = pivot_screen
        angle = _signed_mouse_orbit_angle(px, py, session['start_mx'], session['start_my'], mx, my)

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

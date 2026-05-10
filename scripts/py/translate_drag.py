# -*- coding: utf-8 -*-
"""
Modal viewport translation: enter on translate state, move tracks mouse via
MPxContext.doMotion (and doHold fallback), press confirms.
"""

from __future__ import annotations

import math
from typing import Any, Dict, List, Optional, Tuple

import maya.api.OpenMaya as om
import maya.api.OpenMayaUI as omui
import maya.cmds as cmds


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


def _camera_view_frame(cam_path: om.MDagPath) -> Tuple[om.MVector, om.MVector, om.MVector, om.MVector]:
    """
    Camera eye and orthonormal right, up, forward (forward = view direction) in world space.
    """
    m = cam_path.inclusiveMatrix()
    right = om.MVector(m.getElement(0, 0), m.getElement(1, 0), m.getElement(2, 0)).normalize()
    up = om.MVector(m.getElement(0, 1), m.getElement(1, 1), m.getElement(2, 1)).normalize()
    local_z = om.MVector(m.getElement(0, 2), m.getElement(1, 2), m.getElement(2, 2)).normalize()
    eye = om.MVector(m.getElement(0, 3), m.getElement(1, 3), m.getElement(2, 3))
    forward = (-local_z).normalize()
    return eye, right, up, forward


def _local_axes_world(pivot_path: str) -> Tuple[om.MVector, om.MVector, om.MVector]:
    """Pivot object's local X/Y/Z as unit vectors in world space."""
    sel = om.MSelectionList()
    sel.add(pivot_path)
    dag = sel.getDagPath(0)
    m = dag.inclusiveMatrix()
    lx = om.MVector(m.getElement(0, 0), m.getElement(1, 0), m.getElement(2, 0)).normalize()
    ly = om.MVector(m.getElement(0, 1), m.getElement(1, 1), m.getElement(2, 1)).normalize()
    lz = om.MVector(m.getElement(0, 2), m.getElement(1, 2), m.getElement(2, 2)).normalize()
    return lx, ly, lz


def _world_axes() -> Tuple[om.MVector, om.MVector, om.MVector]:
    return (
        om.MVector(1, 0, 0),
        om.MVector(0, 1, 0),
        om.MVector(0, 0, 1),
    )


def _pick_axis_vector(axis: str, base: str, view_right: om.MVector, view_up: om.MVector,
                      view_forward: om.MVector, pivot_path: Optional[str]) -> om.MVector:
    """Single constrained axis direction in world space."""
    idx = {'x': 0, 'y': 1, 'z': 2}[axis]

    if base == 'screen':
        return [view_right, view_up, view_forward][idx]
    if base == 'world':
        return _world_axes()[idx]
    if pivot_path:
        return _local_axes_world(pivot_path)[idx]
    return _world_axes()[idx]


def _world_units_per_pixel(pivot: om.MVector, eye: om.MVector, cam_path: om.MDagPath,
                           port_w: float, port_h: float) -> Tuple[float, float]:
    """Approximate world translation per pixel at ``pivot`` depth."""
    fn = om.MFnCamera(cam_path)
    if fn.isOrtho():
        ow = float(fn.orthoWidth())
        s = ow / max(port_w, 1.0)
        return s, s

    # verticalFieldOfView() is already in radians in Maya API.
    vfov = float(fn.verticalFieldOfView())
    dist = (pivot - eye).length()
    if dist < 1.0e-4:
        dist = 1.0e-4
    half_h = dist * math.tan(vfov * 0.5)
    sy = (2.0 * half_h) / max(port_h, 1.0)
    sx = sy * (port_w / max(port_h, 1.0))
    print(
        f"[VAM translate] scale perspective: vfov={vfov:.4f} dist={dist:.4f} "
        f"sx={sx:.6f} sy={sy:.6f}"
    )
    return sx, sy


def _plane_delta_raw(dx_px: float, dy_px: float, view_right: om.MVector, view_up: om.MVector,
                     sx: float, sy: float) -> om.MVector:
    """Unconstrained translation in the view plane (screen-style grab)."""
    return view_right * dx_px * sx + view_up * (-dy_px) * sy


def _constrain_world_delta(raw: om.MVector, axis: str, base: str,
                           view_right: om.MVector, view_up: om.MVector,
                           view_forward: om.MVector, pivot_path: Optional[str]) -> om.MVector:
    """Apply axis + base rules to the unconstrained view-plane delta."""
    if axis == 'none':
        if base == 'screen':
            return raw
        return raw

    direction = _pick_axis_vector(axis, base, view_right, view_up, view_forward, pivot_path)
    return direction * raw.dot(direction)


def _selection_world_positions(paths: List[str]) -> Dict[str, Tuple[float, float, float]]:
    out: Dict[str, Tuple[float, float, float]] = {}
    for p in paths:
        t = cmds.xform(p, query=True, translation=True, worldSpace=True)
        out[p] = (float(t[0]), float(t[1]), float(t[2]))
    return out


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


def translate_modal_begin(axis: str, base: str) -> Optional[Dict[str, Any]]:
    """
    Begin modal translation when entering translate state (no mouse button required).

    Mouse origin is set on the first ``translate_modal_update`` (motion / hold event).
    Returns None if no selection or no usable 3D view.
    """
    transforms = cmds.ls(selection=True, type='transform', long=True)
    if not transforms:
        print("[VAM translate] translate_modal_begin: abort — no transform in selection")
        return None

    view = omui.M3dView.active3dView()
    if view is None or not view.isVisible():
        print("[VAM translate] translate_modal_begin: abort — active3dView missing or not visible")
        return None

    port_w = float(view.portWidth())
    port_h = float(view.portHeight())
    if port_w < 1.0 or port_h < 1.0:
        print(f"[VAM translate] translate_modal_begin: abort — bad viewport size {port_w}x{port_h}")
        return None

    cam_path = view.getCamera()
    eye, view_right, view_up, view_forward = _camera_view_frame(cam_path)
    pivot_pt = _selection_pivot(transforms)
    sx, sy = _world_units_per_pixel(pivot_pt, eye, cam_path, port_w, port_h)
    pivot_path = transforms[-1]

    session = {
        'axis': axis,
        'base': base,
        'start_mx': None,
        'start_my': None,
        'sx': sx,
        'sy': sy,
        'eye': eye,
        'view_right': view_right,
        'view_up': view_up,
        'view_forward': view_forward,
        'cam_path': cam_path,
        'port_w': port_w,
        'port_h': port_h,
        'pivot_path': pivot_path,
        'initial_world_t': _selection_world_positions(transforms),
        'paths': transforms,
    }
    print(
        "[VAM translate] translate_modal_begin: OK "
        f"n={len(transforms)} axis={axis!r} base={base!r} port={port_w:.0f}x{port_h:.0f}"
    )
    return session


_DBG_UPDATE_N = 0


def translate_modal_update(session: Dict[str, Any], event: Any) -> None:
    """Apply translation from modal origin to current mouse (origin fixed after first sample)."""
    global _DBG_UPDATE_N
    mx, my = _event_viewport_xy(event)
    if session['start_mx'] is None:
        session['start_mx'] = mx
        session['start_my'] = my
        print(f"[VAM translate] translate_modal_update: anchored mouse origin ({mx:.2f}, {my:.2f})")
        return

    dx = mx - session['start_mx']
    dy = my - session['start_my']

    _DBG_UPDATE_N += 1
    if _DBG_UPDATE_N <= 8 or _DBG_UPDATE_N % 60 == 0:
        print(
            f"[VAM translate] translate_modal_update #{_DBG_UPDATE_N} "
            f"mouse_delta=({dx:.2f},{dy:.2f}) mouse=({mx:.2f},{my:.2f})"
        )

    # Temporary debug mode:
    # bypass camera/axis/base constraint math and map mouse motion directly
    # to world X/Y so movement magnitude is easy to validate.
    # raw = _plane_delta_raw(
    #     dx, dy,
    #     session['view_right'], session['view_up'],
    #     session['sx'], session['sy'],
    # )
    # delta = _constrain_world_delta(
    #     raw,
    #     session['axis'],
    #     session['base'],
    #     session['view_right'],
    #     session['view_up'],
    #     session['view_forward'],
    #     session['pivot_path'],
    # )
    # dxw, dyw, dzw = delta.x, delta.y, delta.z
    dxw = float(dx)
    dyw = float(dy)
    dzw = 0.0
    print(f"dxw: {dxw}, dyw: {dyw}, dzw: {dzw}")

    for path in session['paths']:
        ox, oy, oz = session['initial_world_t'][path]
        print('path: ', path, 'x: ', ox + dxw, 'y: ', oy + dyw, 'z: ', oz + dzw)
        cmds.xform(path, t=(ox + dxw, oy + dyw, oz + dzw), ws=True, a=True)
        #cmds.xform(path, t=(2, 3, 4), ws=True, a=True)


def translate_modal_restore(session: Dict[str, Any]) -> None:
    """Restore world translations captured at modal begin (cancel)."""
    for path, t0 in session['initial_world_t'].items():
        cmds.xform(path, translation=t0, worldSpace=True, absolute=True)

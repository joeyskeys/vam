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
    right = om.MVector(m[0], m[1], m[2]).normalize()
    up = om.MVector(m[4], m[5], m[6]).normalize()
    local_z = om.MVector(m[8], m[9], m[10]).normalize()
    eye = om.MVector(m[12], m[13], m[14])
    forward = (-local_z).normalize()
    return eye, right, up, forward


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
    return sx, sy


def _view_ray_world(view: omui.M3dView, x: float, y: float) -> Tuple[om.MVector, om.MVector]:
    """World-space ray origin + direction from viewport pixel coordinates."""
    ix = int(round(x))
    iy = int(round(y))
    try:
        origin, direction = view.viewToWorld(ix, iy)
    except TypeError:
        # Older signatures require mutable output args.
        p = om.MPoint()
        d = om.MVector()
        view.viewToWorld(ix, iy, p, d)
        origin, direction = p, d
    o = om.MVector(origin.x, origin.y, origin.z)
    v = om.MVector(direction.x, direction.y, direction.z)
    if v.length() > 1.0e-8:
        v.normalize()
    return o, v


def _intersect_ray_plane(ray_o: om.MVector, ray_d: om.MVector,
                         plane_p: om.MVector, plane_n: om.MVector) -> Optional[om.MVector]:
    """Ray-plane intersection in world space."""
    denom = ray_d * plane_n
    if abs(denom) < 1.0e-8:
        return None
    t = ((plane_p - ray_o) * plane_n) / denom
    return ray_o + ray_d * t


def _screen_space_delta(view: omui.M3dView, start_x: float, start_y: float, cur_x: float, cur_y: float,
                        pivot_pt: om.MVector, view_right: om.MVector, view_up: om.MVector,
                        view_forward: om.MVector) -> Optional[om.MVector]:
    """
    Screen-space drag mapped to world by intersecting pick rays against
    a camera-facing plane through the selection pivot.
    """
    so, sd = _view_ray_world(view, start_x, start_y)
    co, cd = _view_ray_world(view, cur_x, cur_y)
    p0 = _intersect_ray_plane(so, sd, pivot_pt, view_forward)
    p1 = _intersect_ray_plane(co, cd, pivot_pt, view_forward)
    if p0 is None or p1 is None:
        return None
    plane_delta = p1 - p0
    return view_right * (plane_delta * view_right) + view_up * (plane_delta * view_up)


def _plane_delta_raw(dx_px: float, dy_px: float, view_right: om.MVector, view_up: om.MVector,
                     sx: float, sy: float) -> om.MVector:
    """Unconstrained translation in the view plane (screen-style grab)."""
    return view_right * dx_px * sx + view_up * dy_px * sy


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


def _axis_direction_for_base(axis: str, base: str, session: Dict[str, Any],
                             view_right: om.MVector, view_up: om.MVector,
                             view_forward: om.MVector) -> Optional[om.MVector]:
    """Get constrained axis direction in world space for the current base."""
    if axis not in ('x', 'y', 'z'):
        return None

    idx = {'x': 0, 'y': 1, 'z': 2}[axis]
    if base == 'local':
        return _local_axes_world(session.get('pivot_path'))[idx]
    if base == 'world':
        return (
            om.MVector(1, 0, 0),
            om.MVector(0, 1, 0),
            om.MVector(0, 0, 1),
        )[idx]
    return (view_right, view_up, view_forward)[idx]


def _apply_axis_constraint(raw: Optional[om.MVector], session: Dict[str, Any],
                           view_right: om.MVector, view_up: om.MVector,
                           view_forward: om.MVector) -> om.MVector:
    """Project raw delta to selected axis according to current base mode."""
    if raw is None:
        return om.MVector(0, 0, 0)

    axis = session.get('axis', 'none')
    if axis == 'none':
        return raw

    direction = _axis_direction_for_base(axis, session.get('base', 'screen'), session, view_right, view_up, view_forward)
    if direction is None:
        return raw
    return direction * (raw * direction)


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


def unfreeze_camera(session: Dict[str, Any]) -> None:
    """Unfreeze camera in the current viewport."""
    cam_path = session['cam_path']
    cmds.camera(cam_path, edit=True, lt=False)


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
    cmds.camera(cam_path, edit=True, lt=True)

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
        'pivot_pt': pivot_pt,
        'initial_world_t': _selection_world_positions(transforms),
        'paths': transforms,
        'cam_path': cam_path,
    }
    return session


_DBG_UPDATE_N = 0


def translate_modal_update(session: Dict[str, Any], event: Any) -> None:
    """Apply translation from modal origin to current mouse (origin fixed after first sample)."""
    global _DBG_UPDATE_N
    mx, my = _event_viewport_xy(event)
    if session['start_mx'] is None:
        session['start_mx'] = mx
        session['start_my'] = my
        return

    dx = mx - session['start_mx']
    dy = my - session['start_my']

    _DBG_UPDATE_N += 1

    if session['base'] == 'screen':
        view = omui.M3dView.active3dView()
        cam_path = view.getCamera()
        _, view_right, view_up, view_forward = _camera_view_frame(cam_path)
        raw = _screen_space_delta(
            view,
            session['start_mx'],
            session['start_my'],
            mx,
            my,
            session['pivot_pt'],
            view_right,
            view_up,
            view_forward,
        )
    else:
        view_right = session['view_right']
        view_up = session['view_up']
        view_forward = session['view_forward']
        sx = session['sx']
        sy = session['sy']
        view = omui.M3dView.active3dView()
        if view is not None and view.isVisible():
            try:
                cam_path = view.getCamera()
                eye, view_right, view_up, view_forward = _camera_view_frame(cam_path)
                port_w = float(view.portWidth())
                port_h = float(view.portHeight())
                if port_w > 0.0 and port_h > 0.0:
                    sx, sy = _world_units_per_pixel(
                        session['pivot_pt'], eye, cam_path, port_w, port_h
                    )
            except Exception:
                pass
        raw = _plane_delta_raw(
            dx, dy,
            view_right, view_up,
            sx, sy,
        )
    delta = _apply_axis_constraint(raw, session, view_right, view_up, view_forward)

    dxw, dyw, dzw = delta.x, delta.y, delta.z

    for path in session['paths']:
        ox, oy, oz = session['initial_world_t'][path]
        cmds.xform(path, t=(ox + dxw, oy + dyw, oz + dzw), ws=True, a=True)


def translate_modal_restore(session: Dict[str, Any]) -> None:
    """Restore world translations captured at modal begin (cancel)."""
    for path, t0 in session['initial_world_t'].items():
        cmds.xform(path, translation=t0, worldSpace=True, absolute=True)
    unfreeze_camera(session)
# -*- coding: utf-8 -*-

import importlib
import os, json

import maya.api.OpenMaya as om
import maya.api.OpenMayaUI as omui
import maya.cmds as cmds

from register_manager import RegisterManager
import rotate_move as rm
import scale_move as sm
import translate_move as tm
from utils import local_axes_world, singleton


def get_vam_core():
    """
    Return the process-wide VamCore singleton from the currently loaded ``core`` module.

    Use this (not ``from core import VamCore``) for callers that must agree with the
    plugin after ``reload(core)``: a cached ``VamCore`` class binds the old
    ``@singleton`` closure. Importing ``get_vam_core`` itself is fine — each call
    still goes through ``importlib.import_module`` to construct the live singleton.
    """
    return importlib.import_module(__name__).VamCore()


@singleton
class VamCore:
    """
    Core singleton for VAM tool state management.

    Implements minimal in-class state transitions without callback hooks.
    """
    
    states = {'normal', 'translate', 'rotate', 'scale', 'register_setup', 'register_picking'}

    # Available transform modes
    trs_modes = ['translate', 'rotate', 'scale']

    bases = ['screen', 'world', 'local',]
    
    def __init__(self):
        """Initialize VamCore with state and default settings."""
        self.transitions = {
            'to_translate': {
                'source': {'normal'},
                'destination': 'translate',
                'shortcuts': (
                    {'key': 'w', 'ctl': False, 'alt': False, 'sht': False, 'is_press': True},
                ),
                'updates': {'trs': 'translate'},
            },
            'to_rotate': {
                'source': {'normal'},
                'destination': 'rotate',
                'shortcuts': (
                    {'key': 'e', 'ctl': False, 'alt': False, 'sht': False, 'is_press': True},
                ),
                'updates': {'trs': 'rotate'},
            },
            'to_scale': {
                'source': {'normal'},
                'destination': 'scale',
                'shortcuts': (
                    {'key': 'r', 'ctl': False, 'alt': False, 'sht': False, 'is_press': True},
                ),
                'updates': {'trs': 'scale'},
            },
            'to_normal': {
                'source': {'normal', 'translate', 'rotate', 'scale', 'register_setup', 'register_picking', 'register_shift_picking', 'register_alt_picking'},
                'destination': 'normal',
                'shortcuts': (
                    {'key': 'q', 'ctl': False, 'alt': False, 'sht': False, 'is_press': True},
                ),
                'updates': {},
            },
            'to_register_setup': {
                'source': {'normal'},
                'destination': 'register_setup',
                'shortcuts': (
                    {'key': 'r', 'ctl': True, 'alt': False, 'sht': False, 'is_press': True},
                ),
                'updates': {},
            },
            'to_register_picking': {
                'source': {'normal'},
                'destination': 'register_picking',
                'shortcuts': (
                    {'key': 't', 'ctl': True, 'alt': False, 'sht': False, 'is_press': True},
                ),
                'updates': {},
            },
            'to_register_shift_picking': {
                'source': {'normal'},
                'destination': 'register_shift_picking',
                'shortcuts': (
                    {'key': 't', 'ctl': True, 'alt': False, 'sht': True, 'is_press': True},
                ),
                'updates': {},
            },
            'to_register_alt_picking': {
                'source': {'normal'},
                'destination': 'register_alt_picking',
                'shortcuts': (
                    {'key': 't', 'ctl': True, 'alt': True, 'sht': False, 'is_press': True},
                ),
                'updates': {},
            },
        }

        # axis map: shortcut -> axis
        self.axes = {
            'none': 'none',
            'x': 'x',
            'y': 'y',
            'z': 'z',
        }
        # Transform settings - shared context across states
        self.trs = 'translate'
        self.axis = 'none'
        self.base = 'screen'
        
        # State-specific data
        self.moving_initial_values = {}
        self.state = 'normal'

        self.register_manager = RegisterManager()

        # Active MPxContext (VamContext) when the VAM tool is on; used to refresh title/help UI.
        self._tool_context = None

        # Live translate drag session (viewport mouse); see translate_drag.py
        self._translate_session = None
        self._rotate_session = None
        self._scale_session = None
        self._modal_camera_path = None
        self._dbg_translate_motion_core = 0
        self._normal_select_press = None
        self._normal_select_current = None
        self._normal_select_dragged = False

        self.key_set = set()
        self.key_mapping = {}
        self.init_config()
        self.init_key_set()
        self.init_key_mapping()

    def init_config(self):
        print('init vam config...')
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'configs/vam_config.json')
        if not os.path.exists(config_path):
            print(f'vam config file not found: {config_path}')
            return

        with open(config_path, 'r') as f:
            config = json.load(f)
        profile_name = config.get('key_profile', 'default_profile.json')
        profile_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'configs/', profile_name)
        if not os.path.exists(profile_path):
            print(f'vam profile file not found: {profile_path}')
            return
        with open(profile_path, 'r') as f:
            profile = json.load(f)

        self.axes = profile.get('axes', {})
        transition_shortcuts = profile.get('transitions', {})
        for transition_name, shortcuts in transition_shortcuts.items():
            self.transitions[transition_name]['shortcuts'] = shortcuts
            print(f'transition {transition_name} shortcuts: {shortcuts}')

        print('vam config initialized')

    def _transition(self, trigger_name):
        """Execute a minimal state transition by trigger name."""
        transition = self.transitions.get(trigger_name)
        if not transition:
            print(f"Warning: Trigger '{trigger_name}' not defined")
            return False

        source_states = transition.get('source', set())
        destination = transition.get('destination')

        if self.state not in source_states:
            print(f"Cannot trigger '{trigger_name}' from state '{self.state}'")
            return False

        prev_state = self.state
        self.state = destination

        if destination in ('translate', 'rotate', 'scale'):
            self._freeze_modal_camera()

        if prev_state == 'translate' and destination != 'translate':
            if self._translate_session is not None:
                tm.translate_modal_restore(self._translate_session)
                self._translate_session = None

        if prev_state == 'scale' and destination != 'scale':
            if self._scale_session is not None:
                sm.scale_modal_restore(self._scale_session)
                self._scale_session = None

        if prev_state == 'rotate' and destination != 'rotate':
            if self._rotate_session is not None:
                rm.rotate_modal_restore(self._rotate_session)
                self._rotate_session = None

        if prev_state in ('translate', 'rotate', 'scale') and destination != prev_state:
            self._unfreeze_modal_camera()

        if destination == 'normal':
            self._reset_axis_base()

        if destination == 'translate':
            self._translate_session = tm.translate_modal_begin(self.axis, self.base)
            if self._translate_session is None:
                self._unfreeze_modal_camera()

        if destination == 'rotate':
            self._rotate_session = rm.rotate_modal_begin(self.axis, self.base)
            if self._rotate_session is None:
                self._unfreeze_modal_camera()

        if destination == 'scale':
            self._scale_session = sm.scale_modal_begin(self.axis, self.base)
            if self._scale_session is None:
                self._unfreeze_modal_camera()

        self.refresh_state_display()
        return True

    def init_key_set(self):
        """Initialize supported hotkey names for VAM mapping."""
        self.key_set.clear()
        for c in range(ord('a'), ord('z') + 1):
            self.key_set.add(chr(c))
        for c in range(ord('0'), ord('9') + 1):
            self.key_set.add(chr(c))

        for f_n in range(1, 13):
            self.key_set.add(f'f{f_n}')

        special_keys = (
            'Up', 'Down', 'Left', 'Right',
            'Home', 'End', 'PageUp', 'PageDown', 'Insert',
            'Return', 'Space',
            'Tab',
            'Escape',
            'Delete', 'Backspace',
        )
        for k in special_keys:
            self.key_set.add(k)

    def add_key_mapping(self, key, ctrl=False, alt=False, shft=False, command='', is_press=True):
        """
        Add or update a hotkey mapping tracked by VamCore.

        Args:
            key (str): Maya hotkey key name.
            ctrl (bool): Ctrl modifier.
            alt (bool): Alt modifier.
            shft (bool): Shift modifier.
            command (str): Maya runtime command name.
            is_press (bool): True for press command, False for release command.
        """
        if key not in self.key_set:
            raise ValueError(f'Unsupported key name: {key}')

        key_name = (key, ctrl, alt, shft, is_press)
        self.key_mapping[key_name] = command

    def remove_key_mapping(self, key, ctrl=False, alt=False, shft=False, is_press=True):
        """Remove a tracked hotkey mapping if present."""
        key_name = (key, ctrl, alt, shft, is_press)
        self.key_mapping.pop(key_name, None)

    @staticmethod
    def _modifier_kwargs(ctrl=False, alt=False, shft=False):
        """Build Maya modifier kwargs from booleans."""
        kwargs = {}
        if ctrl:
            kwargs['ctl'] = True
        if alt:
            kwargs['alt'] = True
        if shft:
            kwargs['sht'] = True
        return kwargs

    def register_hotkey(
        self,
        key,
        command,
        ctrl=False,
        alt=False,
        shft=False,
        is_press=True,
        context_name='vamToolContext',
    ):
        """
        Register one hotkey in Maya and track it in key_mapping.

        Args:
            key (str): Maya hotkey key name.
            command (str): Maya runtime command name.
            ctrl (bool): Ctrl modifier.
            alt (bool): Alt modifier.
            shft (bool): Shift modifier.
            is_press (bool): True for press command, False for release command.
            context_name (str): Maya hotkey context name.
        """
        self.add_key_mapping(
            key=key,
            ctrl=ctrl,
            alt=alt,
            shft=shft,
            command=command,
            is_press=is_press,
        )

        mod_kwargs = self._modifier_kwargs(ctrl=ctrl, alt=alt, shft=shft)
        name_cmd = f"{command}NameCommand"
        cmds.nameCommand(name_cmd, annotation=f"{command}", command=command)

        # Clear any existing mapping for this exact key/modifier in the target context.
        cmds.hotkey(
            keyShortcut=key,
            name='',
            releaseName='',
            ctxClient=context_name,
            **mod_kwargs
        )

        if is_press:
            cmds.hotkey(
                keyShortcut=key,
                name=name_cmd,
                ctxClient=context_name,
                **mod_kwargs
            )
        else:
            cmds.hotkey(
                keyShortcut=key,
                releaseName=name_cmd,
                ctxClient=context_name,
                **mod_kwargs
            )

        mod_desc = '+'.join(k for k, v in [('ctl', ctrl), ('alt', alt), ('sht', shft)] if v) or 'none'
        press_release = 'press' if is_press else 'release'
        print(f"Bound {key} (mods={mod_desc}, {press_release}) to {command} in {context_name}")
        
    def init_key_mapping(self):
        """Initialize default hotkey mappings."""
        self.key_mapping.clear()
        from vam_commands import VAM_HANDLE_KEY_PRESS_COMMAND

        modifier_combinations = (
            (False, False, False),
            (True, False, False),
            (False, True, False),
            (False, False, True),
            (True, True, False),
            (True, False, True),
            (False, True, True),
            (True, True, True),
        )
        for key in self.key_set:
            for ctrl, alt, shft in modifier_combinations:
                self.add_key_mapping(
                    key=key,
                    ctrl=ctrl,
                    alt=alt,
                    shft=shft,
                    command=VAM_HANDLE_KEY_PRESS_COMMAND,
                )

    def get_key_bindings(self):
        """
        Convert tracked key mappings to the tuple format used by Maya registration.

        Returns:
            list[tuple[str, str, bool, dict]]
        """
        bindings = []
        for key_data, command in self.key_mapping.items():
            key, ctrl, alt, shft, is_press = key_data
            bindings.append(
                (
                    key,
                    command,
                    is_press,
                    {'ctl': ctrl, 'alt': alt, 'sht': shft},
                )
            )
        print('bindings', bindings)
        return bindings

    @staticmethod
    def _list_runtime_commands():
        """Return runtime command names with Maya-version compatible queries."""
        query_flags = (
            {'userCommandArray': True},
            {'commandArray': True},
        )
        for flags in query_flags:
            try:
                commands = cmds.runTimeCommand(query=True, **flags)
            except TypeError:
                continue
            if commands:
                return list(commands)
        return []

    def delete_commands_by_category(self, category):
        """
        Delete runtime commands and paired NameCommands for a category.

        The NameCommand deletion follows this project's naming convention:
        ``<runtimeCommandName>NameCommand``.

        Args:
            category (str): Maya runtime command category (for example: ``VAM``).

        Returns:
            dict: Deleted command names:
                {
                    'runtime_commands': [...],
                    'name_commands': [...],
                }
        """
        if not isinstance(category, str) or not category.strip():
            raise ValueError('category must be a non-empty string')
        category = category.strip()

        deleted = {
            'runtime_commands': [],
            'name_commands': [],
        }

        runtime_commands = self._list_runtime_commands()
        for runtime_name in runtime_commands:
            try:
                runtime_category = cmds.runTimeCommand(runtime_name, query=True, category=True)
            except Exception:
                continue

            if runtime_category != category:
                continue

            name_cmd = f"{runtime_name}NameCommand"
            if cmds.nameCommand(name_cmd, exists=True):
                try:
                    cmds.nameCommand(name_cmd, edit=True, delete=True)
                    deleted['name_commands'].append(name_cmd)
                except Exception:
                    pass

            if cmds.runTimeCommand(runtime_name, exists=True):
                try:
                    cmds.runTimeCommand(runtime_name, edit=True, delete=True)
                    deleted['runtime_commands'].append(runtime_name)
                except Exception:
                    pass

        print(
            f"Deleted {len(deleted['runtime_commands'])} runtime commands and "
            f"{len(deleted['name_commands'])} name commands from category '{category}'."
        )
        return deleted
    
    def handle_register_key(self, register_key):
        """
        Hotkey entry for a register key. RegisterManager only binds the key;
        this method applies state-specific behavior (e.g. recall selection).
        """
        if self.state == 'register_setup':
            objects = self.register_manager.get_register_objects(register_key)
            if objects:
                cmds.select(*objects, replace=True)
        else:
            # Default when not in a register-aware state (extended later).
            pass

    def attach_tool_context(self, context):
        """Register the active tool context for UI refresh (call from toolOnSetup)."""
        self._tool_context = context

    def detach_tool_context(self, context=None):
        """Clear the tool context reference (call from toolOffCleanup)."""
        if self._translate_session is not None:
            print("[VAM translate] detach_tool_context: restoring modal session (tool off)")
            tm.translate_modal_restore(self._translate_session)
            self._translate_session = None
        if self._rotate_session is not None:
            print("[VAM rotate] detach_tool_context: restoring modal session (tool off)")
            rm.rotate_modal_restore(self._rotate_session)
            self._rotate_session = None
        if self._scale_session is not None:
            print("[VAM scale] detach_tool_context: restoring modal session (tool off)")
            sm.scale_modal_restore(self._scale_session)
            self._scale_session = None
        self._unfreeze_modal_camera()
        self._tool_context = None

    def _freeze_modal_camera(self):
        """Lock active viewport camera while modal transform is running."""
        if self._modal_camera_path:
            return
        try:
            view = omui.M3dView.active3dView()
            if view is None or not view.isVisible():
                return
            cam_path = view.getCamera()
            cmds.camera(cam_path, edit=True, lt=True)
            self._modal_camera_path = cam_path
        except Exception:
            self._modal_camera_path = None

    def _unfreeze_modal_camera(self):
        """Unlock viewport camera after modal transform exits."""
        cam_path = self._modal_camera_path
        if not cam_path:
            return
        try:
            cmds.camera(cam_path, edit=True, lt=False)
        except Exception:
            pass
        self._modal_camera_path = None

    def _reset_axis_base(self):
        """Reset axis and base to default values."""
        self.axis = 'none'
        self.base = 'screen'

    def _confirm_translate_modal(self):
        """Commit modal translation and return to normal state."""
        print("[VAM translate] _confirm_translate_modal (LMB)")
        self._translate_session = None
        self._reset_axis_base()
        self._transition('to_normal')

    def _confirm_scale_modal(self):
        """Commit modal scaling and return to normal state."""
        print("[VAM scale] _confirm_scale_modal (LMB)")
        self._scale_session = None
        self._reset_axis_base()
        self._transition('to_normal')

    def _confirm_rotate_modal(self):
        """Commit modal rotation and return to normal state."""
        print("[VAM rotate] _confirm_rotate_modal (LMB)")
        self._rotate_session = None
        self._reset_axis_base()
        self._transition('to_normal')

    def sync_translate_modal_constraints(self):
        """Keep translate/rotate/scale modal sessions in sync after axis/base hotkeys."""
        if self.state == 'translate' and self._translate_session:
            self._translate_session['axis'] = self.axis
            self._translate_session['base'] = self.base
        if self.state == 'rotate' and self._rotate_session:
            self._rotate_session['axis'] = self.axis
            self._rotate_session['base'] = self.base
        if self.state == 'scale' and self._scale_session:
            self._scale_session['axis'] = self.axis
            self._scale_session['base'] = self.base

    def handle_viewport_mouse(self, phase, event):
        """
        Translate modal: ``motion`` (doMotion / doHold) tracks mouse move; ``press`` confirms.

        phase: 'motion' | 'press' | 'drag' | 'release'
        """
        if self.state == 'normal' and phase == 'press':
            left_mouse = True
            try:
                button = event.mouseButton()
                left_button = getattr(omui.MEvent, 'kLeftMouse', None)
                if left_button is None:
                    left_button = getattr(omui.MEvent, 'kLeftButton', None)
                if left_button is not None:
                    left_mouse = (button == left_button)
            except Exception:
                pass

            if left_mouse:
                x, y = self._event_screen_xy(event)
                self._normal_select_press = (x, y)
                self._normal_select_current = (x, y)
                self._normal_select_dragged = False
            return

        if self.state == 'normal' and phase == 'drag':
            if self._normal_select_press is not None:
                self._normal_select_dragged = True
                self._normal_select_current = self._event_screen_xy(event)
            return

        if self.state == 'normal' and phase == 'release':
            if self._normal_select_press is None:
                return

            start_x, start_y = self._normal_select_press
            end_x, end_y = self._event_screen_xy(event)

            shift_pressed = False
            try:
                # Maya modifiers bitfield: Shift=1, Caps=2, Ctrl=4, Alt=8.
                shift_pressed = bool(cmds.getModifiers() & 1)
            except Exception:
                pass
            selection_mode = (
                om.MGlobal.kAddToList if shift_pressed else om.MGlobal.kReplaceList
            )

            dx = abs(float(end_x) - float(start_x))
            dy = abs(float(end_y) - float(start_y))
            use_box_select = self._normal_select_dragged and (dx >= 2.0 or dy >= 2.0)

            try:
                if use_box_select:
                    om.MGlobal.selectFromScreen(
                        int(start_x), int(start_y), int(end_x), int(end_y), selection_mode
                    )
                else:
                    om.MGlobal.selectFromScreen(int(end_x), int(end_y), selection_mode)
            except TypeError:
                try:
                    om.MGlobal.selectFromScreen(
                        int(end_x), int(end_y), int(end_x), int(end_y), selection_mode
                    )
                except Exception:
                    pass
            except Exception:
                pass
            finally:
                self._normal_select_press = None
                self._normal_select_current = None
                self._normal_select_dragged = False
            return

        if self.state not in ('translate', 'rotate', 'scale'):
            if phase == 'press':
                print(
                    f"[VAM translate] handle_viewport_mouse press ignored "
                    f"(state={self.state!r}, need translate/rotate/scale)"
                )
            return

        if self.state == 'translate':
            if phase == 'motion':
                if self._translate_session:
                    tm.translate_modal_update(self._translate_session, event)
                return

            if phase == 'press':
                self._confirm_translate_modal()
            return

        if self.state == 'scale':
            if phase == 'motion':
                if self._scale_session:
                    sm.scale_modal_update(self._scale_session, event)
                return

            if phase == 'press':
                self._confirm_scale_modal()
            return

        if self.state == 'rotate':
            if phase == 'motion':
                if self._rotate_session:
                    rm.rotate_modal_update(self._rotate_session, event)
                return

            if phase == 'press':
                self._confirm_rotate_modal()

    def _event_screen_xy(self, event):
        """Extract 2D screen position from Maya event."""
        x = y = 0.0
        try:
            x, y = event.position(om.MSpace.kScreen)
            return float(x), float(y)
        except Exception:
            pass
        try:
            pos = event.position
            if isinstance(pos, (tuple, list)) and len(pos) >= 2:
                return float(pos[0]), float(pos[1])
        except Exception:
            pass
        return x, y

    def get_normal_selection_marquee(self):
        """
        Return marquee rectangle for normal-state drag selection.

        Returns:
            tuple[float, float, float, float] | None: (x1, y1, x2, y2) or None
            when marquee drawing should be hidden.
        """
        if self.state != 'normal':
            return None
        if not self._normal_select_dragged:
            return None
        if self._normal_select_press is None or self._normal_select_current is None:
            return None

        x1, y1 = self._normal_select_press
        x2, y2 = self._normal_select_current
        if abs(x2 - x1) < 2.0 and abs(y2 - y1) < 2.0:
            return None
        return x1, y1, x2, y2

    def get_axis_guide_lines(self):
        """
        Return world-space guide line segments for the active transform axis.

        Returns:
            list[tuple[om.MPoint, om.MPoint]]: Line segments to draw.
        """
        if self.state not in ('translate', 'rotate', 'scale'):
            return []
        if self.axis not in ('x', 'y', 'z'):
            return []
        if self.base not in ('world', 'local'):
            return []

        paths = cmds.ls(selection=True, type='transform', long=True) or []
        idx = {'x': 0, 'y': 1, 'z': 2}[self.axis]

        if self.base == 'world':
            line_len = self._axis_guide_line_length(paths, include_origin=True)
            direction = (
                om.MVector(1, 0, 0),
                om.MVector(0, 1, 0),
                om.MVector(0, 0, 1),
            )[idx]
            return [self._axis_guide_segment(om.MVector(0, 0, 0), direction, line_len)]

        line_len = self._axis_guide_line_length(paths, include_origin=False)
        lines = []
        for path in paths:
            try:
                origin = cmds.xform(path, query=True, translation=True, worldSpace=True)
                direction = local_axes_world(path)[idx]
            except Exception:
                continue
            lines.append(
                self._axis_guide_segment(
                    om.MVector(float(origin[0]), float(origin[1]), float(origin[2])),
                    direction,
                    line_len,
                )
            )
        return lines

    def _axis_guide_line_length(self, paths, include_origin=False):
        """Choose a visible but bounded guide-line length for the current scene/selection."""
        try:
            bbox = cmds.exactWorldBoundingBox(paths) if paths else cmds.exactWorldBoundingBox()
            dx = float(bbox[3]) - float(bbox[0])
            dy = float(bbox[4]) - float(bbox[1])
            dz = float(bbox[5]) - float(bbox[2])
            diag = (dx * dx + dy * dy + dz * dz) ** 0.5
            line_len = max(diag * 1.5, 10.0)
            if include_origin:
                max_extent = max(abs(float(v)) for v in bbox)
                line_len = max(line_len, max_extent * 2.0)
            return line_len
        except Exception:
            return 100.0

    @staticmethod
    def _axis_guide_segment(origin, direction, line_len):
        """Build a centered world-space line segment."""
        direction = om.MVector(direction)
        if direction.length() < 1.0e-8:
            direction = om.MVector(1, 0, 0)
        direction.normalize()
        half = direction * (float(line_len) * 0.5)
        p1 = origin - half
        p2 = origin + half
        return (
            om.MPoint(p1.x, p1.y, p1.z),
            om.MPoint(p2.x, p2.y, p2.z),
        )

    def refresh_state_display(self):
        """Update tool title/help and mark MToolsInfo as dirty."""
        ctx = self._tool_context
        display_state = f"state={self.state} axis={self.axis} base={self.base}"
        if ctx is not None:
            ctx.setTitleString(f"VAM - Vim-like Animation Tool [{display_state}]")
            try:
                ctx.setHelpString(f"VAM {display_state}")
            except Exception:
                pass

        try:
            omui.MToolsInfo.setDirtyFlag()
        except TypeError:
            omui.MToolsInfo.setDirtyFlag(True)
        except Exception:
            pass

    # Query methods
    def get_current_state(self):
        """Get the name of the current state."""
        return self.state


if __name__ == '__main__':
    # Test the state machine
    vam_core = VamCore()
    print(f"Initial state: {vam_core.get_current_state()}")
    print()
    
# -*- coding: utf-8 -*-

import maya.cmds as cmds

from register_manager import RegisterManager
from utils import singleton


@singleton
class VamCore:
    """
    Core singleton for VAM tool state management.

    Implements minimal in-class state transitions without callback hooks.
    """
    
    states = {'normal', 'translate', 'rotate', 'scale', 'register_setup', 'register_picking'}
    transitions = {
        'to_translate': {
            'source': {'normal'},
            'destination': 'translate',
            'shortcuts': (
                {'key': 'w', 'ctl': False, 'alt': False, 'sht': False, 'is_press': True},
                {'key': 'g', 'ctl': False, 'alt': False, 'sht': False, 'is_press': True},
            ),
            'updates': {'trs': 'translate'},
        },
        'to_rotate': {
            'source': {'normal'},
            'destination': 'rotate',
            'shortcuts': (
                {'key': 'r', 'ctl': False, 'alt': False, 'sht': False, 'is_press': True},
            ),
            'updates': {'trs': 'rotate'},
        },
        'to_scale': {
            'source': {'normal'},
            'destination': 'scale',
            'shortcuts': (
                {'key': 's', 'ctl': False, 'alt': False, 'sht': False, 'is_press': True},
            ),
            'updates': {'trs': 'scale'},
        },
        'to_normal': {
            'source': {'normal', 'translate', 'rotate', 'scale', 'register_setup', 'register_picking'},
            'destination': 'normal',
            'shortcuts': (
                {'key': 'Escape', 'ctl': False, 'alt': False, 'sht': False, 'is_press': True},
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
            'shortcuts': (),
            'updates': {},
        },
    }

    # Available transform modes
    trs_modes = ['translate', 'rotate', 'scale']
    axes = ['none', 'x', 'y', 'z']
    bases = ['screen', 'local', 'world']
    
    def __init__(self):
        """Initialize VamCore with state and default settings."""
        # Transform settings - shared context across states
        self.trs = 'translate'
        self.axis = 'none'
        self.base = 'screen'
        
        # State-specific data
        self.moving_initial_values = {}
        self.state = 'normal'

        self.register_manager = RegisterManager()

        self.key_set = set()
        self.key_mapping = {}
        self.init_key_set()
        self.init_key_mapping()

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

        self.state = destination
        return True

    def init_key_set(self):
        """Initialize supported hotkey names for VAM mapping."""
        self.key_set.clear()
        for c in range(ord('a'), ord('z') + 1):
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

        print('handling key:', key)
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

    # Query methods
    def get_current_state(self):
        """Get the name of the current state."""
        return self.state


if __name__ == '__main__':
    # Test the state machine
    vam_core = VamCore()
    print(f"Initial state: {vam_core.get_current_state()}")
    print()
    
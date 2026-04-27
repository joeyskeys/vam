# -*- coding: utf-8 -*-
"""
VAM Commands and Hotkey Context Setup

This module creates Python commands for VAM tool state transitions
and sets up a custom hotkey context that activates when the tool is active.

The separation allows:
- C++ VamContextCommand handles low-level viewport events (mouse, drag)
- Python commands handle state transitions and high-level input
- Hotkey context provides key bindings specific to VAM tool
"""

import maya.cmds as cmds
import maya.mel as mel
from core import VamCore


def _handle_state_switch(key):
    vam_core = VamCore()
    if key == 'w':
        vam_core.to_moving()
        return True
    if key == 'Escape':
        vam_core.to_normal()
        return True
    if key == 'g':
        vam_core.trs = 'translate'
        return True
    if key == 'r':
        vam_core.trs = 'rotate'
        return True
    if key == 's':
        vam_core.trs = 'scale'
        return True
    return False


def _handle_axis_setup(key):
    if key not in ('x', 'y', 'z'):
        return False
    VamCore().axis = key
    return True


def _handle_base_cycle(key):
    if key != 'Tab':
        return False
    vam_core = VamCore()
    bases = vam_core.bases
    vam_core.base = bases[(bases.index(vam_core.base) + 1) % len(bases)]
    return True


def _handle_register_setup(key):
    vam_core = VamCore()
    if vam_core.state != 'register_setup':
        return False
    vam_core.register_manager.set_register_from_selection(key)
    return True


def _handle_register_picking(key):
    vam_core = VamCore()
    if vam_core.state != 'register_picking':
        return False
    objects = vam_core.register_manager.get_register_objects(key)
    if objects:
        cmds.select(*objects, replace=True)
    return True


def vam_handle_key_press(key):
    if _handle_state_switch(key):
        return

    if _handle_axis_setup(key):
        return
    
    if _handle_base_cycle(key):
        return

    if _handle_register_setup(key):
        return

    if _handle_register_picking(key):
        return


# ============================================================================
# Hotkey Context Setup
# ============================================================================

VAM_HOTKEY_SET = "vamToolSet"
VAM_HOTKEY_CONTEXT = "vamToolContext"
VAM_HANDLE_KEY_PRESS_COMMAND = "vamHandleKeyPress"


def begin_vam_tool_hotkey_set():
    """
    Save the active hotkey set, then switch to the VAM hotkey set.

    Creates the VAM set (duplicated from the current set) if it does not exist;
    otherwise switches the current hotkey set to VAM. Call
    restore_vam_tool_hotkey_set with the returned name when the VAM tool exits.

    Returns:
        str | None: Name of the hotkey set that was current before switching.
    """
    previous = cmds.hotkeySet(q=True, current=True)
    if isinstance(previous, (list, tuple)):
        previous = previous[0] if previous else None

    if cmds.hotkeySet(VAM_HOTKEY_SET, exists=True):
        cmds.hotkeySet(VAM_HOTKEY_SET, edit=True, current=True)
    else:
        cmds.hotkeySet(VAM_HOTKEY_SET, current=True)

    print('previous hotkey set:', previous)
    print('switched to vam hotkey set')

    return previous


def restore_vam_tool_hotkey_set(previous_set_name):
    """Restore the hotkey set that was current before begin_vam_tool_hotkey_set."""
    if not previous_set_name:
        return
    if cmds.hotkeySet(previous_set_name, exists=True):
        cmds.hotkeySet(previous_set_name, edit=True, current=True)
    
    print('restored hotkey set:', previous_set_name)


def create_vam_commands():
    """
    Create runtime commands that can be bound to hotkeys.
    
    These commands are registered with Maya's command system using runTimeCommand.
    They can then be assigned to keys via nameCommand.
    """
    commands = [
        {
            'name': VAM_HANDLE_KEY_PRESS_COMMAND,
            'annotation': 'VAM: Unified key press entry',
            'category': 'VAM',
            'command': "from vam_commands import vam_handle_key_press; vam_handle_key_press('')",
        },
    ]
    
    for cmd in commands:
        # Delete if exists
        if cmds.runTimeCommand(cmd['name'], exists=True):
            cmds.runTimeCommand(cmd['name'], edit=True, delete=True)
        
        # Create runtime command
        cmds.runTimeCommand(
            cmd['name'],
            annotation=cmd['annotation'],
            category=cmd['category'],
            command=cmd['command']
        )
        
        print(f"Created runtime command: {cmd['name']}")


def create_vam_hotkey_context():
    """
    Create a custom hotkey context for VAM tool.

    This function only creates/associates the context and does not register
    key bindings. Use register_vam_hotkey_bindings for key registration.
    """
    # Same for context
    if not cmds.hotkeyCtx(te=VAM_HOTKEY_CONTEXT, q=True):
        cmds.hotkeyCtx(ita=('', VAM_HOTKEY_CONTEXT))
        print(f"Created hotkey context: {VAM_HOTKEY_CONTEXT}")
    
    # Associate context with viewport panels (modelPanel)
    # This makes the context active when focus is in a 3D viewport
    cmds.hotkeyCtx(t=VAM_HOTKEY_CONTEXT, ac='modelPanel')
    print(f"Associated {VAM_HOTKEY_CONTEXT} with modelPanel (3D viewports)")
    
def register_vam_hotkey_bindings(key_bindings):
    """
    Register hotkey bindings into VAM hotkey context.

    Args:
        key_bindings (list[tuple[str, str, bool, dict]]): Hotkey definitions
            in the format (key, command_name, is_press, modifier_flags).
    """
    # There's no key pressing handling event in MPxContext.
    # If no corresponding key is registered, tool will exit immediately.
    # Use VamCore single-key registration so runtime updates and initial setup
    # both go through the same code path.
    vam_core = VamCore()
    for key, command_name, is_press, mod_flags in key_bindings:
        vam_core.register_hotkey(
            key=key,
            command=command_name,
            ctrl=bool(mod_flags.get('ctl')),
            alt=bool(mod_flags.get('alt')),
            shft=bool(mod_flags.get('sht')),
            is_press=is_press,
            context_name=VAM_HOTKEY_CONTEXT,
        )


def activate_vam_hotkey_context():
    """
    Activate the VAM hotkey context.
    
    Call this when the VAM tool becomes active.
    Sets the current client to the active modelPanel (3D viewport).
    """
    if not cmds.hotkeyCtx(VAM_HOTKEY_CONTEXT, exists=True):
        print(f"Warning: Hotkey context {VAM_HOTKEY_CONTEXT} does not exist")
        return
    
    # Get the currently active model panel (3D viewport)
    active_panel = cmds.getPanel(withFocus=True)
    
    # Check if it's a model panel (3D viewport)
    if active_panel and cmds.getPanel(typeOf=active_panel) == 'modelPanel':
        # Set this specific modelPanel as the current client for VAM context
        cmds.hotkeyCtx(t=VAM_HOTKEY_CONTEXT, currentClient=active_panel)
        print(f"Activated hotkey context: {VAM_HOTKEY_CONTEXT} for {active_panel}")
    else:
        # Fallback: just set the context type as current
        # This will work with any associated modelPanel
        cmds.hotkeyCtx(t=VAM_HOTKEY_CONTEXT, currentClient='modelPanel')
        print(f"Activated hotkey context: {VAM_HOTKEY_CONTEXT} (generic modelPanel)")



def deactivate_vam_hotkey_context():
    """
    Deactivate the VAM hotkey context and restore default.
    
    Call this when the VAM tool is exited.
    """
    # Return to default hotkey context
    active_panel = cmds.getPanel(withFocus=True)
    cmds.hotkeyCtx(t="Global", cc=active_panel)
    print(f"Deactivated hotkey context, returned to Global")


def setup_vam_hotkeys(key_bindings):
    """
    Complete setup for VAM commands and hotkeys.
    
    Call this during initialization (e.g., in userSetup.py).

    Args:
        key_bindings (list[tuple[str, str, bool, dict]]): Hotkey definitions
            in the format (key, command_name, is_press, modifier_flags).
    """
    print("\n" + "="*60)
    print("Setting up VAM commands and hotkeys...")
    print("="*60)
    
    create_vam_commands()
    create_vam_hotkey_context()
    register_vam_hotkey_bindings(key_bindings)
    
    print("="*60)
    print("VAM hotkey setup complete!")
    print(f"The context '{VAM_HOTKEY_CONTEXT}' will activate when VAM tool is active")
    print("="*60 + "\n")


# ============================================================================
# Helper function to check current context
# ============================================================================

def get_current_hotkey_context():
    """Get the name of the currently active hotkey context."""
    return cmds.hotkeyCtx(query=True, current=True)


def is_vam_context_active():
    """Check if VAM hotkey context is currently active."""
    return get_current_hotkey_context() == VAM_HOTKEY_CONTEXT


if __name__ == '__main__':
    # Test setup
    TEST_KEY_BINDINGS = [
        ('w', 'vamToMoving', True, {}),
        ('Escape', 'vamToNormal', True, {}),
        ('g', 'vamSetTranslate', True, {}),
        ('r', 'vamSetRotate', True, {}),
        ('r', 'vamToRegisterSetup', True, {'ctl': True}),
        ('s', 'vamSetScale', True, {}),
        ('x', 'vamSetAxisX', True, {}),
        ('y', 'vamSetAxisY', True, {}),
        ('z', 'vamSetAxisZ', True, {}),
        ('Tab', 'vamCycleBase', True, {}),
    ]
    setup_vam_hotkeys(TEST_KEY_BINDINGS)

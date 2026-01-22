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


# ============================================================================
# Command Functions - These will be bound to nameCommands
# ============================================================================

def vam_to_moving():
    """Transition to moving state."""
    vam_core = VamCore()
    vam_core.to_moving()


def vam_to_normal():
    """Transition to normal state."""
    vam_core = VamCore()
    vam_core.to_normal()


def vam_to_register_picking():
    """Transition to register picking state."""
    vam_core = VamCore()
    vam_core.to_register_picking()


def vam_set_translate():
    """Set transform mode to translate."""
    vam_core = VamCore()
    vam_core.trs = 'translate'
    print(f"Transform mode: translate")


def vam_set_rotate():
    """Set transform mode to rotate."""
    vam_core = VamCore()
    vam_core.trs = 'rotate'
    print(f"Transform mode: rotate")


def vam_set_scale():
    """Set transform mode to scale."""
    vam_core = VamCore()
    vam_core.trs = 'scale'
    print(f"Transform mode: scale")


def vam_set_axis_x():
    """Constrain to X axis."""
    vam_core = VamCore()
    vam_core.axis = 'x'
    print(f"Axis constraint: X")


def vam_set_axis_y():
    """Constrain to Y axis."""
    vam_core = VamCore()
    vam_core.axis = 'y'
    print(f"Axis constraint: Y")


def vam_set_axis_z():
    """Constrain to Z axis."""
    vam_core = VamCore()
    vam_core.axis = 'z'
    print(f"Axis constraint: Z")


def vam_set_axis_none():
    """Remove axis constraint."""
    vam_core = VamCore()
    vam_core.axis = 'none'
    print(f"Axis constraint: None")


def vam_cycle_base():
    """Cycle through base spaces: screen -> local -> world."""
    vam_core = VamCore()
    bases = ['screen', 'local', 'world']
    current_idx = bases.index(vam_core.base)
    next_idx = (current_idx + 1) % len(bases)
    vam_core.base = bases[next_idx]
    print(f"Base space: {vam_core.base}")


# ============================================================================
# Hotkey Context Setup
# ============================================================================

VAM_HOTKEY_CONTEXT = "vamToolContext"


def create_vam_commands():
    """
    Create runtime commands that can be bound to hotkeys.
    
    These commands are registered with Maya's command system using runTimeCommand.
    They can then be assigned to keys via nameCommand.
    """
    commands = [
        # State transitions
        {
            'name': 'vamToMoving',
            'annotation': 'VAM: Enter moving state',
            'category': 'VAM',
            'command': 'python("from vam_commands import vam_to_moving; vam_to_moving()")'
        },
        {
            'name': 'vamToNormal',
            'annotation': 'VAM: Return to normal state',
            'category': 'VAM',
            'command': 'python("from vam_commands import vam_to_normal; vam_to_normal()")'
        },
        {
            'name': 'vamToRegisterPicking',
            'annotation': 'VAM: Enter register picking state',
            'category': 'VAM',
            'command': 'python("from vam_commands import vam_to_register_picking; vam_to_register_picking()")'
        },
        
        # Transform modes
        {
            'name': 'vamSetTranslate',
            'annotation': 'VAM: Set translate mode',
            'category': 'VAM',
            'command': 'python("from vam_commands import vam_set_translate; vam_set_translate()")'
        },
        {
            'name': 'vamSetRotate',
            'annotation': 'VAM: Set rotate mode',
            'category': 'VAM',
            'command': 'python("from vam_commands import vam_set_rotate; vam_set_rotate()")'
        },
        {
            'name': 'vamSetScale',
            'annotation': 'VAM: Set scale mode',
            'category': 'VAM',
            'command': 'python("from vam_commands import vam_set_scale; vam_set_scale()")'
        },
        
        # Axis constraints
        {
            'name': 'vamSetAxisX',
            'annotation': 'VAM: Constrain to X axis',
            'category': 'VAM',
            'command': 'python("from vam_commands import vam_set_axis_x; vam_set_axis_x()")'
        },
        {
            'name': 'vamSetAxisY',
            'annotation': 'VAM: Constrain to Y axis',
            'category': 'VAM',
            'command': 'python("from vam_commands import vam_set_axis_y; vam_set_axis_y()")'
        },
        {
            'name': 'vamSetAxisZ',
            'annotation': 'VAM: Constrain to Z axis',
            'category': 'VAM',
            'command': 'python("from vam_commands import vam_set_axis_z; vam_set_axis_z()")'
        },
        
        # Base space
        {
            'name': 'vamCycleBase',
            'annotation': 'VAM: Cycle base space (screen/local/world)',
            'category': 'VAM',
            'command': 'python("from vam_commands import vam_cycle_base; vam_cycle_base()")'
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
    
    This context is activated when the VAM tool becomes active,
    and deactivated when the tool is exited.
    """
    # Create hotkey context if it doesn't exist
    if not cmds.hotkeyCtx(VAM_HOTKEY_CONTEXT, exists=True):
        cmds.hotkeyCtx(VAM_HOTKEY_CONTEXT)
        print(f"Created hotkey context: {VAM_HOTKEY_CONTEXT}")
    
    # Define key bindings for VAM tool
    # Format: (key, modifier, command_name, press/release)
    key_bindings = [
        # State transitions
        ('g', '', 'vamToMoving', True),        # 'g' to enter moving (like Blender)
        ('Escape', '', 'vamToNormal', True),   # Escape to return to normal
        
        # Transform modes (when in moving state)
        ('g', '', 'vamSetTranslate', True),    # 'g' for translate (grab)
        ('r', '', 'vamSetRotate', True),       # 'r' for rotate
        ('s', '', 'vamSetScale', True),        # 's' for scale
        
        # Axis constraints
        ('x', '', 'vamSetAxisX', True),        # 'x' to constrain to X
        ('y', '', 'vamSetAxisY', True),        # 'y' to constrain to Y
        ('z', '', 'vamSetAxisZ', True),        # 'z' to constrain to Z
        
        # Base space
        ('Tab', '', 'vamCycleBase', True),     # Tab to cycle base space
    ]
    
    for key, modifier, command_name, is_press in key_bindings:
        # Create name command if it doesn't exist
        name_cmd = f"{command_name}NameCommand"
        if cmds.nameCommand(name_cmd, exists=True):
            cmds.nameCommand(name_cmd, edit=True, command=command_name)
        else:
            cmds.nameCommand(name_cmd, annotation=f"{command_name}", command=command_name)
        
        # Bind to hotkey in VAM context
        press_release = 'press' if is_press else 'release'
        
        # Delete existing binding if present
        try:
            cmds.hotkey(
                keyShortcut=key,
                name='',  # Clear binding
                releaseName='',
                ctxClient=VAM_HOTKEY_CONTEXT
            )
        except:
            pass
        
        # Create new binding
        if is_press:
            cmds.hotkey(
                keyShortcut=key,
                name=name_cmd,
                ctxClient=VAM_HOTKEY_CONTEXT
            )
        else:
            cmds.hotkey(
                keyShortcut=key,
                releaseName=name_cmd,
                ctxClient=VAM_HOTKEY_CONTEXT
            )
        
        print(f"Bound {key} ({press_release}) to {command_name} in {VAM_HOTKEY_CONTEXT}")


def activate_vam_hotkey_context():
    """
    Activate the VAM hotkey context.
    
    Call this when the VAM tool becomes active.
    """
    if cmds.hotkeyCtx(VAM_HOTKEY_CONTEXT, exists=True):
        cmds.hotkeyCtx(VAM_HOTKEY_CONTEXT, edit=True, current=True)
        print(f"Activated hotkey context: {VAM_HOTKEY_CONTEXT}")
    else:
        print(f"Warning: Hotkey context {VAM_HOTKEY_CONTEXT} does not exist")


def deactivate_vam_hotkey_context():
    """
    Deactivate the VAM hotkey context and restore default.
    
    Call this when the VAM tool is exited.
    """
    # Return to default hotkey context
    cmds.hotkeyCtx("default", edit=True, current=True)
    print(f"Deactivated hotkey context, returned to default")


def setup_vam_hotkeys():
    """
    Complete setup for VAM commands and hotkeys.
    
    Call this during initialization (e.g., in userSetup.py).
    """
    print("\n" + "="*60)
    print("Setting up VAM commands and hotkeys...")
    print("="*60)
    
    create_vam_commands()
    create_vam_hotkey_context()
    
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
    setup_vam_hotkeys()

# VAM Tool Architecture

## Overview

VAM (Vim-like Animation Manipulator) is a Maya tool that provides a modal, keyboard-driven interface for animation manipulation, inspired by Vim and Blender.

## Component Structure

```
vam/
├── plugins/py/
│   └── vam_tool.py          # Maya MPxContext plugin (viewport tool)
├── scripts/
│   ├── py/
│   │   ├── core.py          # StateMachine + VamCore state management
│   │   ├── vam_commands.py  # Hotkey commands and context setup
│   │   └── utils.py         # Singleton decorator
│   └── startup/
│       └── userSetup.py     # Maya initialization script
└── docs/
    ├── ARCHITECTURE.md      # This file
    └── CPP_MIGRATION_GUIDE.md  # Guide for C++ migration
```

## Core Components

### 1. StateMachine (core.py)
Generic, declarative state machine library built from scratch.

**Features:**
- States defined as simple lists
- Transitions defined as configuration dicts
- Automatic creation of trigger methods
- Flexible callback system (before/after, on_enter/on_exit)
- No external dependencies

**Example:**
```python
states = ['normal', 'moving', 'register_picking']
transitions = [
    {'trigger': 'to_moving', 'source': 'normal', 'dest': 'moving'},
    {'trigger': 'to_normal', 'source': ['moving', 'register_picking'], 'dest': 'normal'},
]

machine = StateMachine(model=self, states=states, transitions=transitions, initial='normal')
# Automatically creates: self.to_moving(), self.to_normal()
```

### 2. VamCore (core.py)
Application-specific state management using StateMachine.

**States:**
- `normal` - Selection and navigation mode
- `moving` - Modal transform editing (Blender-style)
- `register_picking` - Vim-like register operations (stub)

**Shared Context:**
- `trs` - Transform mode: translate/rotate/scale
- `axis` - Axis constraint: none/x/y/z
- `base` - Coordinate space: screen/local/world

**Event Handlers:**
- `handle_mouse_event()` - Dispatches to state-specific mouse handlers
- `handle_key_event()` - Dispatches to state-specific key handlers
- `update()` - Per-frame update dispatched to current state

### 3. VamContext Plugin (vam_tool.py)
Maya MPxContext that integrates with VamCore.

**Responsibilities:**
- Register as Maya context tool
- Forward viewport events to VamCore
- Activate/deactivate hotkey context
- Handle tool lifecycle (setup/cleanup)

**Maya Context Methods:**
- `toolOnSetup()` - Activate hotkey context, reset to normal state
- `toolOffCleanup()` - Deactivate hotkey context
- `doPress/doDrag/doRelease()` - Forward mouse events to VamCore
- `doKeyDown()` - Handle 'q' and 'Esc' to exit tool

### 4. VAM Commands (vam_commands.py)
Maya command and hotkey system integration.

**Runtime Commands Created:**
- `vamToMoving` - Enter moving state
- `vamToNormal` - Return to normal state
- `vamSetTranslate/Rotate/Scale` - Set transform mode
- `vamSetAxisX/Y/Z` - Set axis constraint
- `vamCycleBase` - Cycle coordinate space

**Hotkey Context:**
- Context name: `vamToolContext`
- Activated when VAM tool is active
- Deactivated when VAM tool exits

**Key Bindings (default):**
- `g` - Enter moving state (grab)
- `r` - Set rotate mode
- `s` - Set scale mode
- `x/y/z` - Constrain to X/Y/Z axis
- `Tab` - Cycle base space
- `Esc` - Return to normal state

## Data Flow

### Tool Activation
```
User: cmds.setToolTo('vam')
  ↓
VamContext.toolOnSetup()
  ↓
VamCore().to_normal()  # Reset state
  ↓
activate_vam_hotkey_context()  # Activate custom keys
```

### Mouse Event
```
Maya Viewport: User clicks mouse
  ↓
VamContext.doPress(event)
  ↓
VamCore().handle_mouse_event(event)
  ↓
Current State Handler (e.g., _handle_mouse_normal)
  ↓
State-specific logic executes
```

### Keyboard Event (via Hotkey Context)
```
Maya: User presses 'g' key
  ↓
Maya Hotkey System (vamToolContext active)
  ↓
vamToMoving nameCommand
  ↓
vam_to_moving() Python function
  ↓
VamCore().to_moving()
  ↓
StateMachine.transition('moving')
  ↓
Callbacks: before_moving() → on_exit_normal() → on_enter_moving()
```

### State Transition Flow
```
Current State: normal
  ↓
Trigger: to_moving()
  ↓
StateMachine checks: Is transition valid from 'normal'?
  ↓ YES
Execute 'before' callback: before_moving()
  ↓
Execute on_exit: on_exit_normal()
  ↓
Change state: normal → moving
  ↓
Execute on_enter: on_enter_moving()
  ↓
Execute 'after' callback (if defined)
  ↓
New State: moving
```

## State Behaviors

### Normal State
**Purpose:** Selection and navigation

**Mouse Events:**
- Click to select controllers
- Drag to marquee select (TODO)

**Key Events:**
- Keyboard shortcuts for selection (TODO)
- Special keys trigger state transitions

**Exit Conditions:**
- Trigger to moving state via hotkey
- Trigger to register_picking state via hotkey

### Moving State
**Purpose:** Modal transform editing (Blender-style)

**Mouse Events:**
- Mouse movement calculates transform delta
- Continuous preview update (non-committed)

**Key Events:**
- `g/r/s` - Set transform mode
- `x/y/z` - Set axis constraint
- `Tab` - Cycle base space
- `Esc` - Return to normal, commit changes

**Data:**
- `moving_initial_values` - Store original transforms for reset

**Exit Conditions:**
- Explicit return to normal (commits changes)
- Cancel operation (reverts to initial values)

### Register Picking State
**Purpose:** Vim-like register operations

**Status:** Stub implementation (future feature)

## Integration with Maya

### Plugin Registration
```python
# plugins/py/vam_tool.py
def initializePlugin(mobj):
    mplugin = om.MFnPlugin(mobj, 'VamPlugin', '1.0', 'Any')
    mplugin.registerContextCommand('vam', VamContextCmd)

def uninitializePlugin(mobj):
    mplugin = om.MFnPlugin(mobj)
    mplugin.deregisterContextCommand('vam')
```

### Startup Sequence
```python
# scripts/startup/userSetup.py
def initialize_vam():
    setup_vam_hotkeys()      # Create runtime commands and hotkey context
    cmds.loadPlugin('vam_tool')  # Load context plugin
    
cmds.evalDeferred("initialize_vam()")
```

### Usage
```python
# Activate tool
cmds.setToolTo('vam')

# Or via MEL
setToolTo vam;
```

## Design Principles

### 1. Declarative Configuration
States and transitions are data, not code:
```python
# Easy to understand and modify
states = ['normal', 'moving', 'register_picking']
transitions = [
    {'trigger': 'to_moving', 'source': 'normal', 'dest': 'moving'},
]
```

### 2. Separation of Concerns
- **StateMachine**: Generic state machine library (reusable)
- **VamCore**: Application logic (VAM-specific)
- **VamContext**: Maya integration (viewport events)
- **vam_commands**: Hotkey integration (user input)

### 3. No External Dependencies
Everything built from scratch:
- No transitions library
- No external state machine
- Pure Python + Maya API

### 4. Maya Conventions
- Uses Maya's hotkey system (`runTimeCommand`, `nameCommand`, `hotkeyCtx`)
- Users can customize through Hotkey Editor
- Follows Maya tool patterns (`MPxContext`)

### 5. Extensibility
Easy to add new:
- States: Add to `states` list
- Transitions: Add to `transitions` list
- Commands: Add function + runtime command
- Hotkeys: Add to `key_bindings` list

## Performance Considerations

### Current (Python)
- ✅ Fast enough for UI interactions
- ✅ Easy to develop and debug
- ✅ Flexible and modifiable

### Future (C++ Context)
If profiling shows bottlenecks:
1. Move VamContext to C++ (viewport events)
2. Keep VamCore in Python (state logic)
3. Keep vam_commands in Python (hotkeys)

See [CPP_MIGRATION_GUIDE.md](CPP_MIGRATION_GUIDE.md) for details.

## Testing

### State Machine
```python
# Test state transitions
vam = VamCore()
assert vam.get_current_state() == 'normal'

vam.to_moving()
assert vam.get_current_state() == 'moving'

vam.to_normal()
assert vam.get_current_state() == 'normal'
```

### Hotkey Context
```python
# Activate tool
cmds.setToolTo('vam')

# Press keys: g, r, s, x, y, z, Tab, Esc
# Verify state changes in console output
```

### Full Integration
```python
# Load plugin
cmds.loadPlugin('vam_tool')

# Activate tool
cmds.setToolTo('vam')

# Use mouse and keyboard
# Verify state changes and transform behavior
```

## Future Enhancements

### Short Term
- [ ] Implement controller selection in normal state
- [ ] Implement transform calculation in moving state
- [ ] Add visual feedback (HUD display)
- [ ] Add undo/redo support

### Medium Term
- [ ] Implement register_picking state
- [ ] Add viewport drawing (transform gizmo)
- [ ] Add snapping options
- [ ] Add numerical input

### Long Term
- [ ] C++ context for performance
- [ ] Custom viewport drawing
- [ ] Animation curves manipulation
- [ ] Timeline scrubbing modes

## Summary

The VAM tool provides a modern, extensible architecture for modal animation manipulation in Maya:

- ✅ Clean state machine from scratch
- ✅ Declarative configuration
- ✅ Maya hotkey integration
- ✅ Extensible design
- ✅ Easy to test and debug
- ✅ Clear migration path to C++

All without external dependencies!

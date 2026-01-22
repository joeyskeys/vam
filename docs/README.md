# VAM Tool Documentation

## Overview

VAM (Vim-like Animation Manipulator) is a Maya tool providing modal, keyboard-driven animation manipulation inspired by Vim and Blender.

## Documentation

1. **[ARCHITECTURE.md](ARCHITECTURE.md)** - Complete system architecture
   - Component structure
   - Data flow diagrams
   - Design principles
   - State behaviors

2. **[KEYBINDINGS.md](KEYBINDINGS.md)** - Key binding reference
   - All keyboard shortcuts
   - Workflow examples
   - Customization guide
   - Troubleshooting

3. **[CPP_MIGRATION_GUIDE.md](CPP_MIGRATION_GUIDE.md)** - C++ migration strategy
   - Architecture diagrams
   - Phase-by-phase migration plan
   - C++ code examples
   - Python/C++ integration patterns

## Quick Start

### Installation

The VAM tool loads automatically when Maya starts (via `userSetup.py`):

```python
# Already done in scripts/startup/userSetup.py
from vam_commands import setup_vam_hotkeys
setup_vam_hotkeys()
cmds.loadPlugin('vam_tool')
```

### Usage

```python
# Activate the tool
cmds.setToolTo('vam')

# Now use keyboard shortcuts:
# - 'g' to enter moving mode
# - 'r' for rotate, 's' for scale
# - 'x', 'y', 'z' for axis constraints
# - 'Esc' to return to normal mode
```

## Key Features

### ✅ Custom State Machine
- Built from scratch (no external dependencies)
- Declarative configuration
- Automatic trigger method generation
- Flexible callback system

### ✅ Maya Integration
- Uses Maya's hotkey context system
- Customizable through Hotkey Editor
- Standard MPxContext plugin
- Event forwarding architecture

### ✅ Modal Interaction
- **Normal State** - Selection and navigation
- **Moving State** - Blender-style modal transforms
- **Register Picking** - Vim-like registers (planned)

### ✅ Extensible Design
- Easy to add states
- Easy to add commands
- Easy to modify key bindings
- Clear separation of concerns

### ✅ Migration Path
- Start with Python (current)
- Move to C++ for performance (optional)
- Keep Python for flexibility
- Documented migration strategy

## Architecture at a Glance

```
┌──────────────────────────────────────────────────┐
│              Maya Viewport                        │
└────────────────┬─────────────────────────────────┘
                 │
                 ▼
┌──────────────────────────────────────────────────┐
│  VamContext (MPxContext)                          │
│  • Viewport event handling                        │
│  • Activates hotkey context                       │
└────────────────┬─────────────────────────────────┘
                 │
        ┌────────┴────────┐
        │                 │
        ▼                 ▼
┌──────────────┐  ┌──────────────────────────┐
│  VamCore     │  │  Hotkey Context          │
│  (Python)    │  │  (nameCommand/hotkey)    │
│              │  │                          │
│  • States    │  │  • Key bindings          │
│  • Logic     │  │  • User commands         │
└──────────────┘  └──────────────────────────┘
```

## File Structure

```
vam/
├── plugins/py/
│   └── vam_tool.py          # Maya context plugin
├── scripts/
│   ├── py/
│   │   ├── core.py          # State machine + VamCore
│   │   ├── vam_commands.py  # Hotkey commands
│   │   └── utils.py         # Utilities
│   └── startup/
│       └── userSetup.py     # Maya startup
└── docs/
    ├── README.md            # This file
    ├── ARCHITECTURE.md      # Architecture details
    ├── KEYBINDINGS.md       # Key binding reference
    └── CPP_MIGRATION_GUIDE.md  # C++ migration guide
```

## Development

### Testing State Machine

```python
# Test in Maya script editor
from core import VamCore

vam = VamCore()
print(vam.get_current_state())  # 'normal'

vam.to_moving()
print(vam.get_current_state())  # 'moving'

vam.to_normal()
print(vam.get_current_state())  # 'normal'
```

### Testing Hotkeys

```python
# Activate tool
cmds.setToolTo('vam')

# Press keys and watch console output:
# 'g' → "Preparing to enter moving mode..."
# 'r' → "Transform mode: rotate"
# 'x' → "Axis constraint: X"
# Esc → "Returning to normal mode..."
```

### Modifying Key Bindings

Edit `scripts/py/vam_commands.py`:

```python
key_bindings = [
    ('g', '', 'vamToMoving', True),     # Modify this
    ('r', '', 'vamSetRotate', True),    # Or this
    # Add new bindings
]

# Restart Maya or reload:
from importlib import reload
import vam_commands
reload(vam_commands)
vam_commands.setup_vam_hotkeys()
```

## Answering Your Question

### How to Combine nameCommand/Hotkey Context with VamContextCommand?

**Answer:** They work together in layers:

1. **VamContextCommand (C++/Python)** - Handles viewport events
   - Mouse clicks, drags, releases
   - Low-level, high-frequency events
   - Forwards to VamCore state machine

2. **Hotkey Context (Python)** - Handles user commands
   - Key bindings specific to VAM tool
   - State transitions
   - High-level actions

3. **Flow:**
```
User activates tool → VamContextCommand.toolOnSetup()
                    → Activates hotkey context
                    
User presses 'g'    → Hotkey system
                    → nameCommand 'vamToMoving'
                    → Python: vam_to_moving()
                    → VamCore.to_moving()
                    → State changes
                    
User moves mouse    → VamContextCommand.doDrag()
                    → VamCore.handle_mouse_event()
                    → Current state handler
                    → Transform calculation
```

### When Migrating to C++:

**C++ handles:**
- Viewport events (doPress, doDrag, doRelease)
- Low-level event processing
- Performance-critical code

**Python handles:**
- State machine logic (flexible)
- Hotkey commands (customizable)
- High-level behaviors (easy to modify)

**They communicate:**
```cpp
// C++ context forwards to Python
MStatus VamContext::doPress(MEvent& event) {
    MGlobal::executePythonCommand(
        "from core import VamCore; "
        "VamCore().handle_mouse_event(None)"
    );
    return MS::kSuccess;
}
```

See [CPP_MIGRATION_GUIDE.md](CPP_MIGRATION_GUIDE.md) for complete examples.

## Why This Design?

### Benefits of Separation:

1. **C++ Context:**
   - Fast viewport event handling
   - Native Maya API integration
   - Stable, compiled code

2. **Python Hotkeys:**
   - Easy to modify key bindings
   - Users can customize via Maya UI
   - No recompilation needed
   - Shows up in Hotkey Editor

3. **Python State Machine:**
   - Rapid development
   - Easy debugging
   - Declarative configuration
   - Can migrate to C++ later if needed

### Best of Both Worlds:
- ✅ Performance where it matters (viewport events)
- ✅ Flexibility where it helps (state logic, key bindings)
- ✅ Standard Maya conventions (hotkey system)
- ✅ User customization support

## Next Steps

### Immediate:
- [x] State machine implementation
- [x] Hotkey context setup
- [x] Basic plugin structure
- [ ] Implement controller selection
- [ ] Implement transform calculation
- [ ] Add visual feedback

### Future:
- [ ] C++ context migration (if needed)
- [ ] Viewport drawing
- [ ] Animation curve manipulation
- [ ] Register system implementation

## Support

For questions or issues:
1. Check [ARCHITECTURE.md](ARCHITECTURE.md) for system details
2. Check [KEYBINDINGS.md](KEYBINDINGS.md) for key reference
3. Check [CPP_MIGRATION_GUIDE.md](CPP_MIGRATION_GUIDE.md) for C++ migration

## Summary

You now have:
- ✅ Custom state machine (no external deps)
- ✅ Maya hotkey integration (nameCommand + hotkeyCtx)
- ✅ Context plugin (event forwarding)
- ✅ Clean architecture (easy to extend)
- ✅ C++ migration path (when needed)
- ✅ Complete documentation

All working together to provide a Vim/Blender-like modal animation interface in Maya!

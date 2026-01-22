# VAM Tool - Key Bindings Reference

## Activation

```python
# Activate VAM tool
cmds.setToolTo('vam')

# Or in MEL
setToolTo vam;
```

## Global Keys (Work in any state when VAM tool is active)

| Key | Action | Description |
|-----|--------|-------------|
| `q` | Exit Tool | Return to Maya select tool |
| `Esc` | Exit Tool | Return to Maya select tool |

## State Transitions

| Key | Action | From State | To State |
|-----|--------|------------|----------|
| `g` | Enter Moving | Normal | Moving |
| `Esc` | Return to Normal | Moving | Normal |

## Moving State Keys

When in **Moving** state, these keys control the transform operation:

### Transform Mode

| Key | Mode | Description |
|-----|------|-------------|
| `g` | Translate | Move/grab objects |
| `r` | Rotate | Rotate objects |
| `s` | Scale | Scale objects |

### Axis Constraints

| Key | Axis | Description |
|-----|------|-------------|
| `x` | X-axis | Constrain to X axis |
| `y` | Y-axis | Constrain to Y axis |
| `z` | Z-axis | Constrain to Z axis |

### Coordinate Space

| Key | Action | Description |
|-----|--------|-------------|
| `Tab` | Cycle Base | Cycle through: Screen → Local → World |

## Workflow Examples

### Example 1: Simple Translation
```
1. Activate tool:       cmds.setToolTo('vam')
2. Select controller:   Click in viewport (Normal state)
3. Enter moving:        Press 'g'
4. Constrain to X:      Press 'x'
5. Move mouse:          Object follows
6. Confirm:             Press Esc (returns to Normal)
```

### Example 2: Rotation with Constraint
```
1. In Normal state:     Select controller
2. Enter moving:        Press 'g'
3. Switch to rotate:    Press 'r'
4. Constrain to Z:      Press 'z'
5. Rotate:              Move mouse
6. Confirm:             Press Esc
```

### Example 3: Local Space Scale
```
1. In Normal state:     Select controller
2. Enter moving:        Press 'g'
3. Switch to scale:     Press 's'
4. Change to local:     Press Tab (until "local")
5. Scale:               Move mouse
6. Confirm:             Press Esc
```

## State Diagram

```
┌─────────────────────────────────────────┐
│           NORMAL STATE                  │
│  • Select controllers                   │
│  • Mouse click selection                │
│  • Keyboard shortcuts                   │
└──────────────┬──────────────────────────┘
               │
               │ Press 'g'
               ▼
┌─────────────────────────────────────────┐
│           MOVING STATE                  │
│  • Press g/r/s → Transform mode         │
│  • Press x/y/z → Axis constraint        │
│  • Press Tab   → Cycle base space       │
│  • Mouse move  → Update transform       │
│  • Press Esc   → Commit & return        │
└──────────────┬──────────────────────────┘
               │
               │ Press Esc
               ▼
         Back to NORMAL
```

## Customization

### Modifying Key Bindings

Edit `scripts/py/vam_commands.py`:

```python
key_bindings = [
    # Format: (key, modifier, command_name, press/release)
    ('g', '', 'vamToMoving', True),        # Change 'g' to another key
    ('r', '', 'vamSetRotate', True),       # Change 'r' to another key
    # Add new bindings here
]
```

### Adding New Commands

1. Add command function in `vam_commands.py`:
```python
def vam_custom_action():
    """Your custom action."""
    vam_core = VamCore()
    # Your logic here
```

2. Register runtime command:
```python
commands = [
    {
        'name': 'vamCustomAction',
        'annotation': 'VAM: Custom action',
        'category': 'VAM',
        'command': 'python("from vam_commands import vam_custom_action; vam_custom_action()")'
    },
]
```

3. Bind to key:
```python
key_bindings = [
    ('c', '', 'vamCustomAction', True),  # 'c' triggers custom action
]
```

4. Reload:
```python
# Restart Maya or reload module
from importlib import reload
import vam_commands
reload(vam_commands)
vam_commands.setup_vam_hotkeys()
```

## Hotkey Context

VAM uses Maya's hotkey context system:

- **Context Name:** `vamToolContext`
- **Active When:** VAM tool is active
- **Inactive When:** Other tools are active

### Checking Active Context

```python
from vam_commands import get_current_hotkey_context, is_vam_context_active

print(get_current_hotkey_context())  # Shows current context
print(is_vam_context_active())       # True if VAM context active
```

### Maya Hotkey Editor

Your VAM commands appear in Maya's Hotkey Editor:
1. Windows → Settings/Preferences → Hotkey Editor
2. Search for "VAM"
3. See all registered VAM commands
4. Users can remap them through the UI

## Implementation Details

### How Hotkeys Work

```
User presses 'g'
  ↓
Maya Hotkey System checks active context
  ↓
vamToolContext is active
  ↓
Looks up 'g' binding in vamToolContext
  ↓
Finds 'vamToMoving' nameCommand
  ↓
Executes 'vamToMoving' runtime command
  ↓
Runs Python: vam_to_moving()
  ↓
Calls: VamCore().to_moving()
  ↓
State changes: normal → moving
```

### Why Use Hotkey Context?

✅ **Better than Context.doKeyDown():**
- Users can customize through Maya UI
- Shows up in Hotkey Editor
- Consistent with Maya conventions
- Easier to maintain
- No recompilation needed

❌ **Context.doKeyDown():**
- Hardcoded in plugin
- Users can't remap
- Requires recompilation to change
- Harder to maintain

## Planned Additions

Future key bindings to be implemented:

### Normal State
- `h/j/k/l` - Vim-like navigation
- `w` - Next controller
- `b` - Previous controller
- `/` - Search/filter
- `v` - Visual selection mode

### Moving State
- `Shift+X/Y/Z` - Constrain to plane (exclude axis)
- `Ctrl+Z` - Undo last transform
- `Enter` - Commit and stay in moving
- Numbers - Numerical input mode

### Register Picking State
- `a-z` - Select register
- `"` - Register prefix
- `@` - Execute register

## Troubleshooting

### Keys Not Working

1. **Check if VAM tool is active:**
```python
cmds.currentCtx()  # Should return 'vam'
```

2. **Check if hotkey context is active:**
```python
from vam_commands import is_vam_context_active
print(is_vam_context_active())  # Should be True
```

3. **Reload hotkeys:**
```python
from vam_commands import setup_vam_hotkeys
setup_vam_hotkeys()
```

4. **Check for conflicts:**
```python
# Check what 'g' is bound to
cmds.hotkey('g', query=True, name=True)
```

### State Not Changing

1. **Check current state:**
```python
from core import VamCore
print(VamCore().get_current_state())
```

2. **Test state transition manually:**
```python
from core import VamCore
vam = VamCore()
vam.to_moving()
print(vam.get_current_state())  # Should be 'moving'
```

3. **Check console output:**
- State changes print messages
- Look for error messages

## References

- [ARCHITECTURE.md](ARCHITECTURE.md) - System architecture overview
- [CPP_MIGRATION_GUIDE.md](CPP_MIGRATION_GUIDE.md) - C++ migration guide
- Maya API Documentation - MPxContext, runTimeCommand, hotkeyCtx

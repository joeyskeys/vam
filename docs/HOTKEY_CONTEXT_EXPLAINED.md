# Maya Hotkey Context System Explained

## Understanding Maya's Hotkey Context

Maya's hotkey system has a hierarchical context structure that determines which key bindings are active based on:
1. **Context Type** - Named context layer (e.g., "vamToolContext")
2. **Client** - Panel type that the context applies to (e.g., "modelPanel")
3. **Current Client** - Specific panel instance (e.g., "modelPanel1")

## The Components

### 1. Context Type
A named layer in the hotkey hierarchy where you define key bindings.

```python
# Create a new context type
cmds.hotkeyCtx(insertTypeAt=('', 'vamToolContext'))
```

### 2. Client (Panel Type)
The **type** of Maya panel the context should be active in. Common clients:

| Client Name | Description |
|------------|-------------|
| `modelPanel` | 3D viewport panels |
| `outlinerPanel` | Outliner panels |
| `hyperGraphPanel` | Hypergraph/Node Editor panels |
| `graphEditor` | Graph Editor panels |
| `timeControl` | Timeline controls |

For a **viewport manipulation tool** like VAM, you want `modelPanel`.

### 3. Current Client (Panel Instance)
A specific instance of a panel type (e.g., "modelPanel1", "modelPanel2", "modelPanel3").

## How VAM Tool Uses It

### Step 1: Create Context Type
```python
# In create_vam_hotkey_context()
if not cmds.hotkeyCtx(typeExists='vamToolContext', query=True):
    cmds.hotkeyCtx(insertTypeAt=('', 'vamToolContext'))
```

Creates the "vamToolContext" layer in the hotkey hierarchy.

### Step 2: Associate with Panel Type
```python
# Associate with viewport panels (modelPanel type)
cmds.hotkeyCtx(type='vamToolContext', addClient='modelPanel')
```

This tells Maya: "vamToolContext hotkeys should work in 3D viewports (modelPanel)."

**Important:** Use `'modelPanel'` (no number suffix) when associating the **type**, not a specific instance.

### Step 3: Bind Keys to Context
```python
# Create runtime command
cmds.runTimeCommand('vamToMoving', command='...')

# Create name command
cmds.nameCommand('vamToMovingNameCommand', command='vamToMoving')

# Bind key in vamToolContext
cmds.hotkey(
    keyShortcut='g',
    name='vamToMovingNameCommand',
    ctxClient='vamToolContext'  # Key binding for this context
)
```

### Step 4: Activate Context for Specific Panel
```python
# When VAM tool becomes active
def activate_vam_hotkey_context():
    # Get the currently focused viewport
    active_panel = cmds.getPanel(withFocus=True)
    
    if cmds.getPanel(typeOf=active_panel) == 'modelPanel':
        # Set this specific modelPanel as current client
        cmds.hotkeyCtx(
            type='vamToolContext',
            currentClient=active_panel  # e.g., 'modelPanel1'
        )
```

This activates the vamToolContext hotkeys **only in the currently focused viewport**.

## Complete Flow

```
User activates VAM tool → VamContext.toolOnSetup()
  ↓
activate_vam_hotkey_context() called
  ↓
Gets focused panel: active_panel = 'modelPanel1'
  ↓
Sets current client: hotkeyCtx(type='vamToolContext', currentClient='modelPanel1')
  ↓
User presses 'g' in modelPanel1
  ↓
Maya checks: Is 'g' bound in active context?
  ↓
Current context hierarchy:
  - vamToolContext (current client: modelPanel1) ← Checks here first
  - Default context
  ↓
Finds: 'g' → 'vamToMovingNameCommand' → 'vamToMoving' runtime command
  ↓
Executes: vam_to_moving() Python function
  ↓
State changes: normal → moving
```

## Why This Matters

### Without Client Association
```python
# BAD: Context not associated with any panel type
cmds.hotkeyCtx('vamToolContext')  # Creates context
# Keys won't work - no client association!
```

### With Client Association
```python
# GOOD: Context associated with modelPanel
cmds.hotkeyCtx('vamToolContext')  # Creates context
cmds.hotkeyCtx(t='vamToolContext', ac='modelPanel')  # Associate with viewports

# When activated with currentClient='modelPanel1'
# Keys will work in that viewport!
```

## Common Panel Types

To find what panels exist in your Maya session:

```python
# List all panels
all_panels = cmds.getPanel(allPanels=True)
print(all_panels)

# List only model panels (3D viewports)
model_panels = cmds.getPanel(type='modelPanel')
print(model_panels)  # ['modelPanel1', 'modelPanel2', ...]

# Get currently focused panel
focused = cmds.getPanel(withFocus=True)
print(focused)  # 'modelPanel1'

# Get panel type
panel_type = cmds.getPanel(typeOf=focused)
print(panel_type)  # 'modelPanel'
```

## Debugging Hotkey Context

### Check if context exists
```python
exists = cmds.hotkeyCtx(typeExists='vamToolContext', query=True)
print(f"Context exists: {exists}")
```

### Check associated clients
```python
clients = cmds.hotkeyCtx(
    type='vamToolContext',
    clientArray=True,
    query=True
)
print(f"Associated clients: {clients}")  # ['modelPanel']
```

### Check current client
```python
current = cmds.hotkeyCtx(
    type='vamToolContext',
    currentClient=True,
    query=True
)
print(f"Current client: {current}")  # 'modelPanel1'
```

### List all context types
```python
all_contexts = cmds.hotkeyCtx(typeArray=True, query=True)
print(f"All context types: {all_contexts}")
# ['vamToolContext', 'Global', ...]
```

## Example: Official Documentation

From Maya's docs, they show:

```python
# Create context
cmds.hotkeyCtx(insertTypeAt=('Global', 'CustomEditor'))

# Associate with panels
cmds.hotkeyCtx(
    type='CustomEditor',
    addClient=['hyperGraphPanel', 'outlinerPanel']  # Multiple clients
)

# Set current client
cmds.hotkeyCtx(
    type='CustomEditor',
    currentClient='hyperGraphPanel'
)
```

**Key insight:** `addClient` uses the **panel type** (no number), while `currentClient` uses a **specific instance** (with number if multiple exist).

## VAM Implementation

### In `vam_commands.py`:

```python
VAM_HOTKEY_CONTEXT = "vamToolContext"

def create_vam_hotkey_context():
    # 1. Create context type
    if not cmds.hotkeyCtx(te=VAM_HOTKEY_CONTEXT, q=True):
        cmds.hotkeyCtx(ita=('', VAM_HOTKEY_CONTEXT))
    
    # 2. Associate with viewport panel type
    cmds.hotkeyCtx(t=VAM_HOTKEY_CONTEXT, ac='modelPanel')
    
    # 3. Bind keys (will work in modelPanel)
    # ... key binding code ...

def activate_vam_hotkey_context():
    # 4. When tool activates, set specific panel as current
    active_panel = cmds.getPanel(withFocus=True)
    
    if cmds.getPanel(typeOf=active_panel) == 'modelPanel':
        cmds.hotkeyCtx(
            t=VAM_HOTKEY_CONTEXT,
            currentClient=active_panel  # Specific instance
        )
```

## Summary

| Component | What to Use | Example |
|-----------|-------------|---------|
| **Create Context** | Context name | `'vamToolContext'` |
| **Associate Client** | Panel type (no number) | `'modelPanel'` |
| **Set Current** | Panel instance (with number) | `'modelPanel1'` |

**The key difference:**
- `addClient='modelPanel'` - Associate with the **type**
- `currentClient='modelPanel1'` - Activate for a **specific instance**

This ensures your hotkeys work in 3D viewports when your tool is active! 🎯

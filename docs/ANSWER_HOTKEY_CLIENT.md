# Answer: What Client Should Be Associated with VAM Hotkey Context?

## Short Answer

Use **`'modelPanel'`** as the client for viewport manipulation tools.

```python
# Associate VAM context with 3D viewports
cmds.hotkeyCtx(type='vamToolContext', addClient='modelPanel')
```

## Why `modelPanel`?

In Maya, different panel types have different names:

| Panel Type | Client Name | Description |
|------------|-------------|-------------|
| **3D Viewport** | `modelPanel` | Where you manipulate objects |
| Outliner | `outlinerPanel` | Hierarchy view |
| Node Editor | `hyperGraphPanel` | Node graph |
| Graph Editor | `graphEditor` | Animation curves |
| Timeline | `timeControl` | Time scrubbing |

Since VAM is a **viewport manipulation tool** (like move, rotate, scale), you want it to work in **3D viewports**, which are `modelPanel` type.

## Important Distinction

### When Associating (Type-level)
```python
# Use panel TYPE (no number suffix)
cmds.hotkeyCtx(t='vamToolContext', addClient='modelPanel')
                                              # ↑ No number!
```

This says: "vamToolContext works in ALL modelPanel instances."

### When Activating (Instance-level)
```python
# Use specific panel INSTANCE (with number)
cmds.hotkeyCtx(t='vamToolContext', currentClient='modelPanel1')
                                                  # ↑ Specific instance!
```

This says: "vamToolContext is currently active in modelPanel1."

## Updated Implementation

The fix has been applied to `scripts/py/vam_commands.py`:

```python
def create_vam_hotkey_context():
    # Create context
    if not cmds.hotkeyCtx(te=VAM_HOTKEY_CONTEXT, q=True):
        cmds.hotkeyCtx(ita=('', VAM_HOTKEY_CONTEXT))
    
    # ✅ ADDED: Associate with viewport panels
    cmds.hotkeyCtx(t=VAM_HOTKEY_CONTEXT, ac='modelPanel')
    # Now the context knows it should work in 3D viewports

def activate_vam_hotkey_context():
    # Get the focused viewport
    active_panel = cmds.getPanel(withFocus=True)
    
    # Check if it's a 3D viewport
    if cmds.getPanel(typeOf=active_panel) == 'modelPanel':
        # ✅ Set this specific viewport as current
        cmds.hotkeyCtx(t=VAM_HOTKEY_CONTEXT, currentClient=active_panel)
```

## How to Find Panel Names

If you want to explore what panels exist:

```python
# In Maya script editor:

# 1. List all panels
print(cmds.getPanel(allPanels=True))

# 2. List only 3D viewports
print(cmds.getPanel(type='modelPanel'))
# Output: ['modelPanel1', 'modelPanel2', 'modelPanel3', 'modelPanel4']

# 3. Get currently focused panel
print(cmds.getPanel(withFocus=True))
# Output: 'modelPanel1' (if viewport is focused)

# 4. Get panel type
panel = cmds.getPanel(withFocus=True)
print(cmds.getPanel(typeOf=panel))
# Output: 'modelPanel'
```

## Why the Confusion?

The official Maya documentation shows examples like:

```python
cmds.hotkeyCtx(t='CustomEditor', ac=['hyperGraphPanel', 'outlinerPanel'])
```

These are **editor-specific contexts** for UI panels. The examples use:
- `hyperGraphPanel` - for Node Editor
- `outlinerPanel` - for Outliner

But for **viewport tools** (like VAM), you need:
- `modelPanel` - for 3D viewports

## The Complete Flow

```
1. Create context type
   └─ cmds.hotkeyCtx(insertTypeAt=('', 'vamToolContext'))

2. Associate with panel type
   └─ cmds.hotkeyCtx(t='vamToolContext', addClient='modelPanel')
       └─ "This context works in all 3D viewports"

3. Bind keys to context
   └─ cmds.hotkey(keyShortcut='g', name='...', ctxClient='vamToolContext')
       └─ "Press 'g' in vamToolContext to trigger command"

4. When tool activates, set current client
   └─ cmds.hotkeyCtx(t='vamToolContext', currentClient='modelPanel1')
       └─ "vamToolContext is now active in modelPanel1"

5. User presses 'g' in modelPanel1
   └─ Maya executes the command bound to 'g' in vamToolContext
```

## Verification

After loading VAM in Maya, you can verify:

```python
# Check association
clients = cmds.hotkeyCtx(t='vamToolContext', ca=True, q=True)
print(f"Associated clients: {clients}")  # Should show ['modelPanel']

# Check if context is active
current = cmds.hotkeyCtx(t='vamToolContext', cc=True, q=True)
print(f"Current client: {current}")  # Should show 'modelPanel1' (or similar)
```

## References

- [Maya hotkeyCtx documentation](https://help.autodesk.com/cloudhelp/2025/ENU/Maya-Tech-Docs/CommandsPython/hotkeyCtx.html)
- `docs/HOTKEY_CONTEXT_EXPLAINED.md` - Detailed explanation
- `docs/KEYBINDINGS.md` - Key binding reference

## Summary

**Client name for viewport tools: `'modelPanel'`**

This makes your VAM tool hotkeys work correctly in Maya's 3D viewports! ✅

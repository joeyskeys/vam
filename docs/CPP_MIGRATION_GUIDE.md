# VAM Tool: C++ Migration Guide

## Architecture Overview

The VAM tool uses a clean separation between low-level viewport interactions and high-level state management:

```
┌─────────────────────────────────────────────────────────────┐
│                      Maya Viewport                           │
└───────────┬─────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────┐
│         VamContext (C++/Python - MPxContext)                 │
│  ┌────────────────────────────────────────────────────┐    │
│  │ • doPress()      - Low-level mouse events          │    │
│  │ • doDrag()       - Mouse movement tracking          │    │
│  │ • doRelease()    - Mouse button release             │    │
│  │ • toolOnSetup()  - Tool activation                  │    │
│  │ • toolOffCleanup() - Tool deactivation              │    │
│  └────────────────────────────────────────────────────┘    │
└───────────┬─────────────────────────────────────────────────┘
            │
            ├─── Forwards events to ────►  VamCore (Python)
            │                              State Machine
            │
            └─── Activates/Deactivates ──► Hotkey Context
                                           (Python Commands)

┌─────────────────────────────────────────────────────────────┐
│               Hotkey Context (Python)                        │
│  ┌────────────────────────────────────────────────────┐    │
│  │  Key Bindings:                                      │    │
│  │  • 'g' → vamToMoving()     (state transition)       │    │
│  │  • 'r' → vamSetRotate()    (mode change)            │    │
│  │  • 'x' → vamSetAxisX()     (axis constraint)        │    │
│  │  • Esc → vamToNormal()     (exit modal)             │    │
│  └────────────────────────────────────────────────────┘    │
└───────────┬─────────────────────────────────────────────────┘
            │
            ▼
┌─────────────────────────────────────────────────────────────┐
│              VamCore State Machine (Python)                  │
│  ┌────────────────────────────────────────────────────┐    │
│  │  States: [normal, moving, register_picking]         │    │
│  │  Transitions: [to_moving, to_normal, ...]           │    │
│  │  Context: {trs, axis, base}                         │    │
│  └────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

## Current Implementation (Python)

### 1. VamContextCommand (Python - plugins/py/vam_tool.py)
Currently in Python, handles:
- Maya context tool registration
- Mouse event forwarding to VamCore
- Hotkey context activation/deactivation

### 2. VamCore (Python - scripts/py/core.py)
State machine and logic:
- State definitions and transitions
- Transform settings (trs, axis, base)
- Event handlers per state

### 3. VAM Commands (Python - scripts/py/vam_commands.py)
Hotkey-bound commands:
- Runtime commands via `runTimeCommand()`
- Hotkey context via `hotkeyCtx()`
- Key bindings via `hotkey()`

## Migration to C++ Architecture

### Phase 1: Move VamContext to C++ (Recommended First Step)

**File: plugins/cpp/vam_tool.cpp**

```cpp
#include <maya/MPxContext.h>
#include <maya/MPxContextCommand.h>
#include <maya/MEvent.h>
#include <maya/MGlobal.h>
#include <maya/MFnPlugin.h>

// Forward declare Python interface
void activateVamHotkeyContext();
void deactivateVamHotkeyContext();
void forwardMouseEventToCore(MEvent& event);
void forwardKeyEventToCore(MEvent& event);

class VamContext : public MPxContext {
public:
    VamContext() {
        setTitleString("VAM - Vim-like Animation Tool");
        setCursor(MCursor::crossHairCursor);
    }
    
    void toolOnSetup(MEvent& event) override {
        // Activate Python hotkey context
        MGlobal::executePythonCommand(
            "from vam_commands import activate_vam_hotkey_context; "
            "activate_vam_hotkey_context()"
        );
        
        // Initialize Python state machine to normal
        MGlobal::executePythonCommand(
            "from core import VamCore; "
            "VamCore().to_normal()"
        );
        
        MGlobal::displayInfo("VAM Tool Active");
    }
    
    void toolOffCleanup() override {
        // Deactivate Python hotkey context
        MGlobal::executePythonCommand(
            "from vam_commands import deactivate_vam_hotkey_context; "
            "deactivate_vam_hotkey_context()"
        );
        
        MGlobal::displayInfo("VAM Tool Deactivated");
    }
    
    MStatus doPress(MEvent& event) override {
        // Forward to Python VamCore for state-specific handling
        MString pythonCmd = 
            "from core import VamCore; "
            "VamCore().handle_mouse_event(None)";  // Pass event data if needed
        MGlobal::executePythonCommand(pythonCmd);
        
        return MS::kSuccess;
    }
    
    MStatus doDrag(MEvent& event) override {
        // Forward to Python VamCore
        MGlobal::executePythonCommand(
            "from core import VamCore; "
            "VamCore().handle_mouse_event(None)"
        );
        
        return MS::kSuccess;
    }
    
    MStatus doRelease(MEvent& event) override {
        // Forward to Python VamCore
        MGlobal::executePythonCommand(
            "from core import VamCore; "
            "VamCore().handle_mouse_event(None)"
        );
        
        return MS::kSuccess;
    }
};

class VamContextCmd : public MPxContextCommand {
public:
    MPxContext* makeObj() override {
        return new VamContext();
    }
    
    static void* creator() {
        return new VamContextCmd();
    }
};

// Plugin registration
MStatus initializePlugin(MObject obj) {
    MFnPlugin plugin(obj, "VAM Plugin", "1.0", "Any");
    
    MStatus status = plugin.registerContextCommand(
        "vam",
        VamContextCmd::creator
    );
    
    return status;
}

MStatus uninitializePlugin(MObject obj) {
    MFnPlugin plugin(obj);
    return plugin.deregisterContextCommand("vam");
}
```

**Benefits:**
- ✅ Better performance for viewport events
- ✅ Python still handles all state management
- ✅ Hotkeys still work through Python commands
- ✅ Easy to implement - minimal C++ code

### Phase 2: Move Core Logic to C++ (Advanced)

If you want maximum performance, move the state machine to C++:

**File: plugins/cpp/vam_core.h**

```cpp
#pragma once
#include <string>
#include <unordered_map>
#include <functional>

class VamStateMachine {
public:
    struct Transition {
        std::string trigger;
        std::vector<std::string> sources;
        std::string dest;
        std::function<void()> before;
        std::function<void()> after;
    };
    
    VamStateMachine(
        const std::string& initial,
        const std::vector<std::string>& states,
        const std::vector<Transition>& transitions
    );
    
    bool executeTransition(const std::string& trigger);
    std::string getCurrentState() const { return currentState_; }
    bool isState(const std::string& state) const { return currentState_ == state; }

private:
    std::string currentState_;
    std::unordered_map<std::string, std::vector<Transition>> transitionMap_;
    std::function<void(const std::string&)> onEnterCallback_;
    std::function<void(const std::string&)> onExitCallback_;
};

class VamCore {
public:
    static VamCore& instance();  // Singleton
    
    // State transitions
    void toMoving();
    void toNormal();
    void toRegisterPicking();
    
    // Transform settings
    void setTrs(const std::string& mode);
    void setAxis(const std::string& axis);
    void setBase(const std::string& base);
    
    // Event handlers
    void handleMouseEvent(MEvent& event);
    void handleKeyEvent(MEvent& event);
    
    std::string getCurrentState() const;

private:
    VamCore();
    VamStateMachine machine_;
    
    // Transform settings
    std::string trs_;
    std::string axis_;
    std::string base_;
};
```

**But keep Python commands for hotkeys:**

The Python commands in `vam_commands.py` now call into C++:

```python
def vam_to_moving():
    """Transition to moving state - calls C++ backend."""
    maya.cmds.vamTransition(state='moving')  # C++ command

def vam_set_translate():
    """Set transform mode - calls C++ backend."""
    maya.cmds.vamSetMode(mode='translate')  # C++ command
```

## Why This Separation?

### C++ Context Command Benefits:
1. **Performance**: Mouse events happen at viewport refresh rate (60+ fps)
2. **Native Integration**: Better Maya API integration
3. **Stability**: Less overhead than Python callbacks

### Python Hotkey Commands Benefits:
1. **Flexibility**: Easy to modify key bindings without recompiling
2. **Maya Integration**: Uses Maya's built-in hotkey system
3. **User Customization**: Users can remap keys through Maya preferences
4. **Development Speed**: Iterate quickly on key bindings and behaviors

## Key Design Decisions

### 1. Hotkey Context vs Context Tool Key Events

**Hotkey Context (Recommended):**
```python
# Registered commands that work everywhere in Maya
cmds.hotkey(key='g', name='vamToMoving', ctxClient='vamToolContext')
```

**Context Tool doKeyDown (Not Recommended for Actions):**
```cpp
// Only works when tool is active, harder to customize
MStatus doKeyDown(MEvent& event) {
    if (event.key() == 'g') {
        // Handle 'g' key
    }
}
```

**Why Hotkey Context is Better:**
- Users can remap keys through Maya UI
- Commands show up in Hotkey Editor
- Consistent with Maya conventions
- Easier to maintain

### 2. Event Forwarding Pattern

The C++ context acts as a "thin" viewport event handler:

```cpp
// C++ handles low-level events
MStatus doPress(MEvent& event) {
    // Get mouse position, button, modifiers (fast C++)
    short x, y;
    event.getPosition(x, y);
    
    // Forward to state machine (Python or C++)
    forwardMouseEvent(x, y, event.mouseButton());
    
    return MS::kSuccess;
}
```

Python state machine decides what to do:
```python
def _handle_mouse_normal(self, event):
    # In normal state: select controllers
    if event.button == 'left':
        self.select_at_cursor(event.x, event.y)
```

## Migration Steps

### Immediate (Current State):
- [x] Python VamContext
- [x] Python VamCore state machine
- [x] Python hotkey commands and context
- [x] All working together

### Step 1: C++ Context Command
1. Create `plugins/cpp/vam_tool.cpp`
2. Implement VamContext in C++
3. Keep Python calls for state machine
4. Keep Python hotkey commands unchanged
5. Update CMakeLists.txt or compile script

### Step 2: Performance Optimization (Optional)
1. Profile to find bottlenecks
2. Move hot code paths to C++ if needed
3. Keep high-level state management in Python
4. Keep hotkey commands in Python

### Step 3: C++ Core (If Needed)
1. Only if profiling shows Python is bottleneck
2. Create C++ state machine
3. Expose C++ commands to Python
4. Keep Python wrapper commands for hotkeys

## Testing Plan

### Test Python Implementation:
```python
# In Maya script editor
from core import VamCore
vam = VamCore()
print(vam.get_current_state())  # 'normal'
vam.to_moving()
print(vam.get_current_state())  # 'moving'
```

### Test Hotkey Context:
```python
# Activate tool
cmds.setToolTo('vam')

# Try keys: g, r, s, x, y, z, Tab, Esc
# Should see state changes in console
```

### Test C++ Context (After Migration):
```cpp
// Compile and load plugin
cmds.loadPlugin('vam_tool')
cmds.setToolTo('vam')

// Test mouse and keyboard events
// Python hotkeys should still work
```

## Conclusion

The current architecture provides:
- ✅ Clean separation of concerns
- ✅ Easy migration path to C++
- ✅ Python flexibility for state management
- ✅ Maya-standard hotkey system
- ✅ User customization support

Start with Python, profile if needed, migrate to C++ gradually.

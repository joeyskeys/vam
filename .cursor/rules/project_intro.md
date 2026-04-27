---
applyIntelligently: true
---

## Vam

### Project Description

This's a maya plugin which trying to mimic the vim's input experience in maya when creating animation.

### Design Detail

1. plugins/vam_tool.py provides a omui.MPxContext class to create a tool, same like the move, rotation tool, for user to do animation related work in a isolated environment inside maya.

2. omui.MPxContext class only has methods for mouse related event handling, the keyboard events are special and cannot be handled in a MPxContext method. It should be setup via the cmds.hotkey command in a specialized hotkey context associated with this tool.

3. since each key press will be an isolated event, a unified event handling logic is applied to realize a vim-like features, check scripts/py/vam_commands.py vam_handle_key_press function.
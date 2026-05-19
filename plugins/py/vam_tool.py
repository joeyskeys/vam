# -*- coding: utf-8 -*-

import sys
import os
from importlib import reload

import maya.api.OpenMaya as om
import maya.api.OpenMayaUI as omui
import maya.api.OpenMayaRender as omr
import maya.cmds as cmds

import core
reload(core)

# Import hotkey context functions (will be available after setup)
try:
    from vam_commands import (
        activate_vam_hotkey_context,
        begin_vam_tool_hotkey_set,
        deactivate_vam_hotkey_context,
        restore_vam_tool_hotkey_set,
    )
    HOTKEY_CONTEXT_AVAILABLE = True
except ImportError:
    HOTKEY_CONTEXT_AVAILABLE = False
    print("Warning: vam_commands not available, hotkey context will not be activated")


def maya_useNewAPI():
    pass


class VamRenderOverride(omr.MRenderOverride):
    def __init__(self, name, vc):
        super(VamRenderOverride, self).__init__(name)
        self._ops = [
            omr.MSceneRender('vamSceneRender'),
            VamGuidingLineOp('vamGuidingLineOp', vc),
            omr.MPresentTarget('vamPresentTarget'),
        ]
        self._op_index = 0

    def supportedDrawAPIs(self):
        return omr.MRenderer.kAllDevices

    def startOperationIterator(self):
        self._op_index = 0
        return True

    def renderOperation(self):
        if 0 <= self._op_index < len(self._ops):
            return self._ops[self._op_index]
        return None

    def nextRenderOperation(self):
        self._op_index += 1
        return self._op_index < len(self._ops)


class VamContext(omui.MPxContext):
    """
    Maya context for VAM tool.
    
    This context forwards all events to the VamCore state machine,
    allowing different states to handle events appropriately.
    """
    
    def __init__(self):
        super(VamContext, self).__init__()
        self.setTitleString("VAM - Vim-like Animation Tool")
        # Sets the cursor icon
        self.setCursor(omui.MCursor.kCrossHairCursor)
        
        # Shared singleton (use accessor so hotkeys and tool agree after reload(core))
        self.vam_core = core.get_vam_core()
        self._dbg_motion_i = 0
        self._dbg_hold_i = 0
        self._dbg_drag_i = 0
        self._dbg_press_i = 0
        self._render_override = None

    @staticmethod
    def _alt_pressed(event):
        """Best-effort Alt modifier check across Maya API variants."""
        try:
            mods = event.modifiers()
            alt_mask = getattr(omui.MEvent, 'kAltModifier', None)
            if alt_mask is not None:
                return bool(mods & alt_mask)
        except Exception:
            pass
        try:
            # Maya modifiers bitfield: Shift=1, Caps=2, Ctrl=4, Alt=8.
            return bool(cmds.getModifiers() & 8)
        except Exception:
            return False

    def _should_block_alt_navigation(self, event):
        """
        Block Alt+mouse during modal transform states.

        This avoids camera tumble/pan/dolly from changing the view basis mid-modal.
        """
        return (
            self.vam_core.get_current_state() in ('translate', 'rotate', 'scale')
            and self._alt_pressed(event)
        )

    def toolOnSetup(self, event):
        """Called when tool becomes active."""
        print("VAM Tool Active")
        self.vam_core.attach_tool_context(self)
        self.vam_core.refresh_state_display()
        current_state = self.vam_core.get_current_state()
        om.MGlobal.displayInfo(
            f"VAM: Modal tool active. State={current_state}. Press 'q' or 'Esc' to exit."
        )
        
        if HOTKEY_CONTEXT_AVAILABLE:
            self._vam_prev_hotkey_set = begin_vam_tool_hotkey_set()
            activate_vam_hotkey_context()
        else:
            self._vam_prev_hotkey_set = None

    def toolOffCleanup(self):
        """Called when tool is deactivated."""
        print("VAM Tool Deactivated")
        self._deregister_render_override()
        self.vam_core.detach_tool_context(self)

        if HOTKEY_CONTEXT_AVAILABLE:
            deactivate_vam_hotkey_context()
            restore_vam_tool_hotkey_set(getattr(self, "_vam_prev_hotkey_set", None))

    def doPress(self, event, drawMgr, frameContext):
        """
        Handle Mouse Down events.
        
        Forward to state machine for processing by current state.
        """
        self.vam_core.handle_viewport_mouse('press', event)

    def doPtrMoved(self, event, drawMgr, frameContext):
        """Mouse move in the viewport (no button drag); drives modal translate."""
        self.vam_core.handle_viewport_mouse('motion', event)

    def doHold(self, event, drawMgr, frameContext):
        """Some Maya builds use hold instead of motion for passive ticks; same handler."""
        pass
    
    def doRelease(self, event, drawMgr, frameContext):
        """
        Handle Mouse Release events.
        
        Forward to state machine for processing by current state.
        """
        self.vam_core.handle_viewport_mouse('release', event)
    
    def doDrag(self, event, drawMgr, frameContext):
        """
        Mouse drag (button held). Used by normal-state marquee selection.
        """
        if self._should_block_alt_navigation(event):
            return
        self.vam_core.handle_viewport_mouse('drag', event)
        marquee = self.vam_core.get_normal_selection_marquee()
        if not marquee or drawMgr is None:
            return

        x1, y1, x2, y2 = marquee
        try:
            drawMgr.beginDrawable()
            try:
                drawMgr.setColor(om.MColor((1.0, 1.0, 1.0, 0.9)))
                drawMgr.setLineWidth(1.0)
                drawMgr.setLineStyle(omr.MUIDrawManager.kDashed)
            except Exception:
                pass

            p1 = om.MPoint(x1, y1, 0.0)
            p2 = om.MPoint(x2, y1, 0.0)
            p3 = om.MPoint(x2, y2, 0.0)
            p4 = om.MPoint(x1, y2, 0.0)
            drawMgr.line2d(p1, p2)
            drawMgr.line2d(p2, p3)
            drawMgr.line2d(p3, p4)
            drawMgr.line2d(p4, p1)
        except Exception:
            pass
        finally:
            try:
                drawMgr.endDrawable()
            except Exception:
                pass
        
class VamContextCmd(omui.MPxContextCommand):
    def __init__(self):
        super(VamContextCmd, self).__init__()

    def makeObj(self):
        return VamContext()
    

def initializePlugin(mobj):
    mplugin = om.MFnPlugin(mobj, 'VamPlugin', '1.0', 'Any')
    try:
        mplugin.registerContextCommand('vamCmd', VamContextCmd)
    except:
        raise Exception('failed to register vam command')
    

def uninitializePlugin(mobj):
    mplugin = om.MFnPlugin(mobj)
    try:
        mplugin.deregisterContextCommand('vamCmd')
    except:
        raise Exception('failed to deregister vam command')
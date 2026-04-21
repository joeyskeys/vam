# -*- coding: utf-8 -*-

import sys
import os
from importlib import reload

import maya.api.OpenMaya as om
import maya.api.OpenMayaUI as omui
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
        
        # Get VamCore singleton instance
        self.vam_core = core.VamCore()

    def toolOnSetup(self, event):
        """Called when tool becomes active."""
        print("VAM Tool Active")
        om.MGlobal.displayInfo("VAM: Modal tool active. Press 'q' or 'Esc' to exit.")
        
        if HOTKEY_CONTEXT_AVAILABLE:
            self._vam_prev_hotkey_set = begin_vam_tool_hotkey_set()
            activate_vam_hotkey_context()
        else:
            self._vam_prev_hotkey_set = None

    def toolOffCleanup(self):
        """Called when tool is deactivated."""
        print("VAM Tool Deactivated")
        
        if HOTKEY_CONTEXT_AVAILABLE:
            deactivate_vam_hotkey_context()
            restore_vam_tool_hotkey_set(getattr(self, "_vam_prev_hotkey_set", None))

    def doPress(self, event, drawMgr, frameContext):
        """
        Handle Mouse Down events.
        
        Forward to state machine for processing by current state.
        """
        # Forward event to state machine
        self.vam_core.handle_mouse_event(event)
    
    def doRelease(self, event, drawMgr, frameContext):
        """
        Handle Mouse Release events.
        
        Forward to state machine for processing by current state.
        """
        # Forward event to state machine
        self.vam_core.handle_mouse_event(event)
    
    def doDrag(self, event, drawMgr, frameContext):
        """
        Handle Mouse Drag events.
        
        Forward to state machine for processing by current state.
        """
        # Forward event to state machine
        self.vam_core.handle_mouse_event(event)
        

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
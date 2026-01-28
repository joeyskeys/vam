# -*- coding: utf-8 -*-

import sys
import os

import maya.api.OpenMaya as om
import maya.api.OpenMayaUI as omui
import maya.cmds as cmds

from core import VamCore

# Import hotkey context functions (will be available after setup)
try:
    from vam_commands import activate_vam_hotkey_context, deactivate_vam_hotkey_context
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
        self.vam_core = VamCore()

    def toolOnSetup(self, event):
        """Called when tool becomes active."""
        print("VAM Tool Active")
        om.MGlobal.displayInfo("VAM: Modal tool active. Press 'q' or 'Esc' to exit.")
        
        # Ensure we're in normal state when tool activates
        self.vam_core.to_normal()
        
        # Activate VAM hotkey context
        if HOTKEY_CONTEXT_AVAILABLE:
            activate_vam_hotkey_context()

    def toolOffCleanup(self):
        """Called when tool is deactivated."""
        print("VAM Tool Deactivated")
        
        # Return to normal state when tool is deactivated
        self.vam_core.to_normal()
        
        # Deactivate VAM hotkey context
        if HOTKEY_CONTEXT_AVAILABLE:
            deactivate_vam_hotkey_context()

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
        
    def doKeyDown(self, event):
        """
        Handle Keyboard Input while tool is active.
        
        Forward to state machine for processing by current state.
        """
        key = event.key()
        
        # 'q' key (standard Maya exit) or Esc - always exit tool
        if key == 113 or key == 4100: 
            print("Exiting VAM Tool...")
            # Switch back to the standard Select Tool
            cmds.setToolTo('selectSuperContext')
            return
        
        # Forward keyboard event to state machine
        self.vam_core.handle_key_event(event)


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
import maya.api.OpenMaya as om
import maya.api.OpenMayaUI as omui
import maya.cmds as cmds


def maya_useNewAPI():
    pass


class VamContext(omui.MPxContext):
    def __init__(self):
        super(VamContext, self).__init__()
        self.setTitleString("My Custom Plugin Tool")
        # Sets the cursor icon (e.g., crosshair, pencil, etc.)
        self.setCursor(omui.MCursor.kCrossHairCursor)

    def toolOnSetup(self, event):
        print("Modal Tool Active: Hotkeys are now restricted.")
        om.MGlobal.displayInfo("MyTool: Click to act, Press 'q' or 'Esc' to exit.")

    def doPress(self, event, drawMgr, frameContext):
        """Handle Mouse Down"""
        # Detect which button was pressed
        button = event.mouseButton()
        if button == event.kLeftMouse:
            print("Left Click: Performing Action...")
        
    def doKeyDown(self, event):
        """Handle Keyboard Input while tool is active"""
        key = event.key()
        
        # 'q' key (standard Maya exit) or Esc
        if key == 113 or key == 4100: 
            print("Exiting Tool...")
            # Switch back to the standard Select Tool
            cmds.setToolTo('selectSuperContext')
        else:
            # Let Maya handle other keys or block them
            super(VamContext, self).doKeyDown(event)


class VamContextCmd(omui.MPxContextCommand):
    def __init__(self):
        super(VamContextCmd, self).__init__()

    def makeObj(self):
        return VamContext()
    

def initializePlugin(mobj):
    mplugin = om.MFnPlugin(mobj, 'VamPlugin', '1.0', 'Any')
    try:
        mplugin.registerContextCommand('vam', VamContextCmd)
    except:
        raise Exception('failed to register vam')
    

def uninitializePlugin(mobj):
    mplugin = om.MFnPlugin(mobj)
    try:
        mplugin.deregisterContextCommand('vam')
    except:
        raise Exception('failed to deregister vam')
# -*- coding: utf-8 -*-
"""Add VAM to Maya's built-in tool shelf (select / move / rotate toolbar)."""

import os
import traceback

import maya.cmds as cmds
import maya.mel as mel

VAM_TOOL_NAME = 'vam'
VAM_TOOL_BUTTON = 'vamToolButton'
VAM_TOOL_ICON = 'vam_tool.xpm'


def _repo_icons_dir():
    """Return the vam package icons directory (sibling of scripts/)."""
    return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'icons')


def _find_builtin_tool_shelf_parent():
    """
    Locate the layout that holds Maya's default tool buttons (move, rotate, etc.).

    Uses the move tool button as an anchor so we stay on the left tool shelf, not
    the tabbed shelf tabs at the top.
    """
    for button in cmds.lsUI(type='toolButton') or []:
        try:
            if cmds.toolButton(button, query=True, tool=True) == 'moveSuperContext':
                return cmds.control(button, query=True, parent=True)
        except Exception:
            continue

    # Fallback used in Autodesk's MPxContext examples (top tool shelf tab).
    try:
        g_shelf = mel.eval('global string $gShelfTopLevel; $temp = $gShelfTopLevel')
        general = f'{g_shelf}|General'
        if cmds.layout(general, exists=True):
            return general
    except Exception:
        pass

    return None


def setup_vam_tool_button(tool_name=VAM_TOOL_NAME, button_name=VAM_TOOL_BUTTON):
    """
    Create or update the VAM toolButton on Maya's built-in tool shelf.

    Must run after the VAM context exists (``cmds.vamCmd('vam')``).

    Returns:
        str | None: Full UI path of the tool button, or None on failure.
    """
    if not cmds.pluginInfo('vam_tool', query=True, loaded=True):
        print('Warning: vam_tool plugin not loaded')
        return None

    try:
        cmds.vamCmd(tool_name)
    except Exception:
        print('Warning: failed to create VAM tool context')
        print(traceback.format_exc())
        return None

    if cmds.toolButton(button_name, exists=True):
        cmds.toolButton(button_name, edit=True, tool=tool_name)
        print(f'VAM tool button updated: {button_name}')
        return cmds.toolButton(button_name, query=True, fullPathName=True)

    parent = _find_builtin_tool_shelf_parent()
    if not parent:
        print('Warning: Maya tool shelf parent not found; deferring VAM tool button')
        return None

    icon_dir = _repo_icons_dir()
    if os.path.isdir(icon_dir) and icon_dir not in (os.environ.get('XBMLANGPATH') or '').split(os.pathsep):
        os.environ['XBMLANGPATH'] = icon_dir + (os.pathsep + os.environ['XBMLANGPATH'] if os.environ.get('XBMLANGPATH') else '')

    cmds.setParent(parent)
    cmds.toolButton(
        button_name,
        collection='toolCluster',
        tool=tool_name,
        annotation='VAM - Vim-like Animation Tool',
        toolImage1=(tool_name, VAM_TOOL_ICON),
    )
    full_path = cmds.toolButton(button_name, query=True, fullPathName=True)
    print(f'VAM tool button created: {full_path}')
    return full_path


def setup_vam_tool_button_deferred(tool_name=VAM_TOOL_NAME, button_name=VAM_TOOL_BUTTON):
    """Deferred wrapper; retries once if the tool shelf is not built yet."""

    def _try_create(attempt):
        result = setup_vam_tool_button(tool_name=tool_name, button_name=button_name)
        if result is None and attempt < 1:
            cmds.evalDeferred(lambda: _try_create(attempt + 1), lowestPriority=True)

    cmds.evalDeferred(lambda: _try_create(0), lowestPriority=True)

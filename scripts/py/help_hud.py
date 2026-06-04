# -*- coding: utf-8 -*-
"""Viewport HUD brief manual for VAM (cmds.headsUpDisplay)."""

import maya.cmds as cmds

VAM_HELP_HUD_PREFIX = 'vamHelpHud'
VAM_HELP_HUD_SECTION = 0  # left column of the viewport HUD grid

VAM_MANUAL_LINES = (
    'VAM - Vim-like Animation Tool',
    '',
    'Modes:',
    '  w / e / r     translate, rotate, scale',
    '  q             return to normal',
    '  Esc           exit VAM tool',
    '',
    'Axes (in TRS mode):',
    '  1 / 2 / 3     x / y / z',
    '  Tab           cycle screen / world / local',
    '',
    'Registers:',
    '  Ctrl+R        assign selection to letter',
    '  Ctrl+T        recall (replace)',
    '  Ctrl+Shift+T  add to selection',
    '  Ctrl+Alt+T    remove from selection',
    '',
    'Copy / paste:',
    '  Ctrl+C        copy mode (w / e / r / a)',
    '  Ctrl+V        paste transform',
    '  Ctrl+Z        undo',
    '',
    '  h             toggle this help',
)


def _hud_name(index):
    return f'{VAM_HELP_HUD_PREFIX}_{index}'


def _list_vam_help_huds():
    hud_list = cmds.headsUpDisplay(listHeadsUpDisplays=True) or []
    return [name for name in hud_list if name.startswith(VAM_HELP_HUD_PREFIX)]


def is_vam_help_hud_visible():
    """True when any VAM help HUD block exists."""
    return bool(_list_vam_help_huds())


def remove_vam_help_hud():
    """Remove all VAM help HUD blocks."""
    for hud_name in _list_vam_help_huds():
        try:
            cmds.headsUpDisplay(hud_name, remove=True)
        except Exception:
            pass


def _mid_left_start_block(section=VAM_HELP_HUD_SECTION):
    """Pick a starting block near the vertical middle of the left HUD column."""
    try:
        last = cmds.headsUpDisplay(lastOccupiedBlock=True, section=section)
        if last is None:
            last = 0
        last = int(last)
    except Exception:
        last = 0

    line_count = len(VAM_MANUAL_LINES)
    if last <= 2:
        return 4
    # Leave room above; keep the block stack inside the column when possible.
    return max(4, min(last + 1, max(4, 12 - line_count)))


def show_vam_help_hud():
    """Create multi-line help HUD in the left-mid viewport area."""
    remove_vam_help_hud()

    start_block = _mid_left_start_block()
    for index, line in enumerate(VAM_MANUAL_LINES):
        cmds.headsUpDisplay(
            _hud_name(index),
            section=VAM_HELP_HUD_SECTION,
            block=start_block + index,
            blockSize='small',
            blockAlignment='left',
            label=line,
            labelFontSize='small',
            labelWidth=300,
            allowOverlap=True,
        )


def hide_vam_help_hud():
    """Hide help HUD and reset toggle state."""
    remove_vam_help_hud()


def toggle_vam_help_hud():
    """Toggle the brief VAM manual HUD on or off."""
    if is_vam_help_hud_visible():
        hide_vam_help_hud()
        return False
    show_vam_help_hud()
    return True

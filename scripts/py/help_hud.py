# -*- coding: utf-8 -*-
"""Viewport HUD brief manual for VAM (cmds.headsUpDisplay)."""

import maya.cmds as cmds

VAM_HELP_HUD_PREFIX = 'vamHelpHud'
# Prefer left columns; try top-left then bottom-left if crowded.
VAM_HELP_HUD_SECTIONS = (0, 5, 1)

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


def _vam_help_hud_names():
    hud_list = cmds.headsUpDisplay(listHeadsUpDisplays=True) or []
    return [
        name for name in hud_list
        if name == VAM_HELP_HUD_PREFIX or name.startswith(f'{VAM_HELP_HUD_PREFIX}_')
    ]


def _next_free_block(section):
    """Return the next unoccupied block index in a HUD section."""
    block = cmds.headsUpDisplay(nextFreeBlock=section)
    if block is None:
        return None
    return int(block)


def remove_vam_help_hud():
    """Remove all VAM help HUD blocks."""
    for hud_name in _vam_help_hud_names():
        try:
            cmds.headsUpDisplay(hud_name, remove=True)
        except Exception:
            pass


def show_vam_help_hud():
    """Create multi-line help HUD in the left viewport column."""
    remove_vam_help_hud()

    section = VAM_HELP_HUD_SECTIONS[0]
    for candidate in VAM_HELP_HUD_SECTIONS:
        if _next_free_block(candidate) is not None:
            section = candidate
            break
    else:
        cmds.warning('VAM help HUD: no free HUD blocks available.')
        return

    # headsUpDisplay labels do not honor newlines; one block per line.
    for index, line in enumerate(VAM_MANUAL_LINES):
        block = _next_free_block(section)
        if block is None:
            cmds.warning(
                f'VAM help HUD: no free blocks left in section {section} '
                f'(stopped at line {index + 1}).'
            )
            break
        cmds.headsUpDisplay(
            f'{VAM_HELP_HUD_PREFIX}_{index}',
            section=section,
            block=block,
            blockSize='small',
            blockAlignment='left',
            label=line or ' ',
            labelFontSize='small',
            labelWidth=320,
        )


def hide_vam_help_hud():
    """Hide help HUD."""
    remove_vam_help_hud()


def toggle_vam_help_hud():
    """Toggle the brief VAM manual HUD on or off."""
    if _vam_help_hud_names():
        remove_vam_help_hud()
        return False
    show_vam_help_hud()
    return True

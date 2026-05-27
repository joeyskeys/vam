#!/usr/bin/env python
# -*- coding: utf-8 -*-
# author: Joey Skeys

import maya.cmds as cmds
import traceback
import sys
import os
from importlib import reload


def initialize_vam():
    try:
        print("vam initializing...")

        # Setup VAM commands and hotkey context
        try:
            from vam_commands import setup_vam_hotkeys, begin_vam_tool_hotkey_set, restore_vam_tool_hotkey_set
            from core import VamCore

            # ensure the hotkey set is set to the vam tool set
            previous_hotkey_set = begin_vam_tool_hotkey_set()
            key_bindings = VamCore().get_key_bindings()
            setup_vam_hotkeys(key_bindings)
            restore_vam_tool_hotkey_set(previous_hotkey_set)

        except Exception as e:
            print("Warning: Failed to setup VAM hotkeys:")
            print(traceback.format_exc())

        # setup menus

        # load nodes
        cmds.loadPlugin('vam_tool')

        # create a context command instance
        #cmds.vamCmd('vam')

        try:
            from vam_tool_shelf import setup_vam_tool_button_deferred
            setup_vam_tool_button_deferred()
        except Exception:
            print("Warning: Failed to create VAM tool shelf button:")
            print(traceback.format_exc())

        print("vam initialized successfully")
    except Exception as e:
        print("Error in vam initialization:")
        print(traceback.format_exc())


cmds.evalDeferred("initialize_vam()")

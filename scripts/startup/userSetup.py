#!/usr/bin/env python
# -*- coding: utf-8 -*-
# author: Joey Skeys

import maya.cmds as cmds
import traceback
import sys
import os
from importlib import reload


from tools import basic_test
reload(basic_test)

def initialize_vam():
    try:
        print("vam initializing...")

        # Setup VAM commands and hotkey context
        try:
            from vam_commands import setup_vam_hotkeys
            from core import VamCore
            key_bindings = VamCore().get_key_bindings()
            setup_vam_hotkeys(key_bindings)
        except Exception as e:
            print("Warning: Failed to setup VAM hotkeys:")
            print(traceback.format_exc())

        # setup menus

        # load nodes
        cmds.loadPlugin('vam_tool')

        # create a context command instance
        cmds.vamCmd('vam')

        print("vam initialized successfully")
    except Exception as e:
        print("Error in vam initialization:")
        print(traceback.format_exc())


cmds.evalDeferred("initialize_vam()")

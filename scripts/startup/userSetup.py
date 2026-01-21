#!/usr/bin/env python
# -*- coding: utf-8 -*-
# author: Joey Skeys

import maya.cmds as cmds
import traceback
from importlib import reload

from tools import basic_test
reload(basic_test)

def initialize_vam():
    try:
        print("vam initializing...")

        # setup menus

        # load nodes
        cmds.loadPlugin('vam_tool')

        # test
        basic_test.test_tool()

        print("vam initialized successfully")
    except Exception as e:
        print("Error in vam initialization:")
        print(traceback.format_exc())


cmds.evalDeferred("initialize_vam()")

# -*- coding: utf-8 -*-

import maya.cmds as cmds


class RegisterManager:
    """
    Minimal Vim-like register handling for VAM.

    Stores register -> object mappings and dynamically binds register keys to
    select the mapped object in a given hotkey context.
    """

    def __init__(self, hotkey_context='vamToolContext', category='VAM'):
        self.hotkey_context = hotkey_context
        self.category = category

    def set_register_from_selection(self, register_key):
        """
        Save current selection into a register and bind that key.

        Args:
            register_key (str): Single key used as register name and hotkey.

        Returns:
            str: The registered object long name.
        """
        if not self._validate_register_key(register_key):
            return False
        selection = cmds.ls(sl=True, long=True) or []
        if not selection:
            return False

        self._bind_key_to_object(register_key, selection)
        return True

    def _validate_register_key(self, register_key):
        if not isinstance(register_key, str) or len(register_key) != 1:
            return False
        return True

    def _bind_key_to_object(self, register_key, selection):
        if not cmds.hotkeyCtx(self.hotkey_context, exists=True):
            raise RuntimeError(f"Hotkey context does not exist: {self.hotkey_context}")

        runtime_name = f"vamSelectRegister_{register_key}"
        name_cmd = f"{runtime_name}NameCommand"
        command = (
            "import maya.cmds as cmds;"
            f"objs={str(selection)}; "
            "cmds.select(*obj, r=True)"
        )

        if cmds.runTimeCommand(runtime_name, exists=True):
            cmds.runTimeCommand(runtime_name, edit=True, delete=True)
        cmds.runTimeCommand(
            runtime_name,
            annotation=f"VAM register select ({register_key})",
            category=self.category,
            command=command,
        )

        cmds.nameCommand(
            name_cmd,
            annotation=f"VAM register select ({register_key})",
            command=runtime_name,
        )

        cmds.hotkey(
            keyShortcut=register_key,
            name='',
            releaseName='',
            ctxClient=self.hotkey_context,
        )
        cmds.hotkey(
            keyShortcut=register_key,
            name=name_cmd,
            ctxClient=self.hotkey_context,
        )

# -*- coding: utf-8 -*-


class RegisterManager:
    """
    Minimal Vim-like register storage for VAM.

    This class only stores and returns register data. Maya interactions
    (selection query/apply) are handled by command handlers.
    """

    def __init__(self):
        # register_key -> list of object long names (selection targets)
        self._register_objects = {}

    def set_register_from_selection(self, register_key, selection):
        """
        Save provided selection into a register.

        Args:
            register_key (str): Single key used as register name and hotkey.
            selection (list[str] | tuple[str]): Object long names to store.

        Returns:
            bool: True if register saved; otherwise False.
        """
        if not selection:
            return False

        self._bind_key_to_object(register_key, selection)
        return True

    def get_register_objects(self, register_key):
        """Return stored object paths for a register, or None if unknown."""
        return self._register_objects.get(register_key)

    def _bind_key_to_object(self, register_key, selection):
        self._register_objects[register_key] = list(selection)

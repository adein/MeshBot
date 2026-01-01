import os
import importlib.util
import logging

from core.event_bus import EventBus
from interfaces.bot_module import BotModule
from services.meshtastic_service import MeshtasticService


MODULES_DIR = "./modules"


class PluginManager:
    """
    Plugin Manager to discover and load BotModule classes.
    """

    def __init__(self, config, global_services: dict, my_node: str):
        self.modules_dir = MODULES_DIR
        self.config = config
        self.services: dict = global_services
        self.my_node_id: str = my_node
        self.event_bus: EventBus = self.services.get('bus')
        self.mesh_service: MeshtasticService = self.services.get('mesh')
        self.loaded_modules: dict[str, BotModule] = {}
        self.logger = logging.getLogger("Core.PluginManager")

    def discover_and_load(self):
        """
        Scans the modules directory and loads valid BotModule classes.
        """
        self.logger.debug("Scanning for modules in %s...", self.modules_dir)
        if not os.path.exists(self.modules_dir):
            self.logger.error("Directory %s not found.", self.modules_dir)
            return
        for filename in os.listdir(self.modules_dir):
            if filename.endswith(".py") and not filename.startswith("__"):
                self._load_single_file(filename)

    def _load_single_file(self, filename: str):
        module_name = filename[:-3]
        file_path = os.path.join(self.modules_dir, filename)
        self.logger.debug("Loading module file: %s", file_path)
        try:
            # Dynamic import magic
            spec = importlib.util.spec_from_file_location(
                module_name, file_path)
            if spec and spec.loader:
                py_mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(py_mod)
                # Inspect module for BotModule subclasses
                self._register_classes_from_module(py_mod, module_name)
        except Exception as e:
            self.logger.error(
                "Failed to load file %s: %s", filename, e, exc_info=True)

    def _register_classes_from_module(self, py_mod, module_name_from_file: str):
        for attribute_name in dir(py_mod):
            attribute = getattr(py_mod, attribute_name)
            # Check if it's a class, inherits from BotModule, and IS NOT BotModule itself
            if isinstance(attribute, type) and issubclass(attribute, BotModule) and attribute is not BotModule:
                # Configuration key MUST match the file name
                mod_config = self.config.get('modules', {}).get(
                    module_name_from_file, {})

                try:
                    instance = attribute(
                        name=module_name_from_file,
                        config=mod_config,
                        global_services=self.services,
                        my_node=self.my_node_id,
                    )
                    self.loaded_modules[module_name_from_file] = instance
                    self.logger.info(
                        "Successfully registered module: %s", module_name_from_file)
                except Exception as e:
                    self.logger.error(
                        "Error instantiating %s: %s", attribute_name, e, exc_info=True)

    def get_module(self, name: str) -> BotModule | None:
        """
        Retrieve a loaded module by name.

        :param name: Name of the module to retrieve
        :type name: str
        :return: The BotModule instance if found, else None.
        :rtype: BotModule | None
        """
        return self.loaded_modules.get(name)

    def get_all_modules(self) -> dict[str, BotModule]:
        """
        Retrieve all loaded modules.

        :return: Dictionary of all loaded modules keyed by their names.
        :rtype: dict[str, BotModule]
        """
        return self.loaded_modules

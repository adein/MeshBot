import os
import importlib.util
import logging
from interfaces.bot_module import BotModule

class PluginManager:
    def __init__(self, modules_dir, config, event_bus, my_node, mesh_svc):
        self.modules_dir = modules_dir
        self.config = config
        self.event_bus = event_bus
        self.my_node_id = my_node
        self.mesh_service = mesh_svc
        self.loaded_modules = {}
        self.logger = logging.getLogger("Core.PluginManager")

    def discover_and_load(self):
        """
        Scans the modules directory and loads valid BotModule classes.
        """
        self.logger.info(f"Scanning for modules in {self.modules_dir}...")
        
        if not os.path.exists(self.modules_dir):
            self.logger.error(f"Directory {self.modules_dir} not found.")
            return

        for filename in os.listdir(self.modules_dir):
            if filename.endswith(".py") and not filename.startswith("__"):
                self._load_single_file(filename)

    def _load_single_file(self, filename):
        module_name = filename[:-3]
        file_path = os.path.join(self.modules_dir, filename)

        try:
            # Dynamic import magic
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            if spec and spec.loader:
                py_mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(py_mod)
                
                # Inspect module for BotModule subclasses
                self._register_classes_from_module(py_mod, module_name)
        except Exception as e:
            self.logger.error(f"Failed to load file {filename}: {e}")

    def _register_classes_from_module(self, py_mod, module_name_from_file):
        for attribute_name in dir(py_mod):
            attribute = getattr(py_mod, attribute_name)
            
            # Check if it's a class, inherits from BotModule, and IS NOT BotModule itself
            if isinstance(attribute, type) and issubclass(attribute, BotModule) and attribute is not BotModule:
                
                # Use the class name or file name as the key? Let's use file name for now.
                # Configuration key matches the file name (e.g. 'sample_task')
                mod_config = self.config.get('modules', {}).get(module_name_from_file, {})
                
                try:
                    instance = attribute(
                        name=module_name_from_file,
                        config=mod_config,
                        event_bus=self.event_bus,
                        my_node=self.my_node_id,
                        mesh_svc=self.mesh_service
                    )
                    self.loaded_modules[module_name_from_file] = instance
                    self.logger.info(f"Successfully registered module: {module_name_from_file}")
                except Exception as e:
                    self.logger.error(f"Error instantiating {attribute_name}: {e}")

    def get_module(self, name):
        return self.loaded_modules.get(name)

    def get_all_modules(self):
        return self.loaded_modules

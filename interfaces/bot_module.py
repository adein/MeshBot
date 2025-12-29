from abc import ABC, abstractmethod
import logging

class BotModule(ABC):
    """
    The contract that all modules must follow.
    """
    def __init__(self, name, config, global_services, my_node=None):
        self.name = name
        self.config = config
        self.services = global_services
        self.my_node_id = my_node
        self.db = self.services.get('db')
        self.event_bus = self.services.get('bus')
        self.mesh_service = self.services.get('mesh')
        self.logger = logging.getLogger(name)

    @abstractmethod
    def execute(self):
        """
        The logic to run on the schedule.
        """
        pass

    def is_enabled(self):
        return self.config.get('enabled', False)

from abc import ABC, abstractmethod
import logging

class BotModule(ABC):
    """
    The contract that all modules must follow.
    """
    def __init__(self, name, config, event_bus=None, my_node=None, mesh_svc=None):
        self.name = name
        self.config = config
        self.event_bus = event_bus
        self.my_node_id = my_node
        self.mesh_service = mesh_svc
        self.logger = logging.getLogger(name)

    @abstractmethod
    def execute(self):
        """
        The logic to run on the schedule.
        """
        pass

    def is_enabled(self):
        return self.config.get('enabled', False)

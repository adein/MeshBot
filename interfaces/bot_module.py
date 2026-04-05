from abc import ABC, abstractmethod
import logging

from core.database import Database
from core.event_bus import EventBus
from services.meshtastic_service import MeshtasticService


class BotModule(ABC):
    """
    Abstract base class for bot modules.
    """

    def __init__(self, name: str, config, root_config, global_services: dict, my_node: str):
        self.name: str = name
        self.config = config
        self.root_config = root_config
        self.services: dict = global_services
        self.my_node_id: str = my_node
        self.db: Database = self.services.get('db')
        self.event_bus: EventBus = self.services.get('bus')
        self.mesh_service: MeshtasticService = self.services.get('mesh')
        self.logger = logging.getLogger(name)

    @abstractmethod
    def execute(self):
        """
        The logic to run on the schedule.
        """
        # Do nothing in the abstract class
        pass

    def is_enabled(self) -> bool:
        """
        Check if the module is enabled in the configuration.

        :return: True if enabled, False otherwise
        :rtype: bool
        """
        return self.config.get('enabled', False)

    def is_dm_only(self) -> bool:
        """
        Check if the module should respond only to DMs.

        :return: True if enabled, False otherwise
        :rtype: bool
        """
        return self.config.get('dm_only', False)

from abc import ABC, abstractmethod

from core.event_bus import EventBus


class BotService(ABC):
    """
    Abstract base class for bot services.
    """

    def __init__(self, event_bus: EventBus, config):
        self.event_bus: EventBus = event_bus
        self.config = config

    @abstractmethod
    def connect(self):
        """Called on bot startup. Should start any background threads/connections."""
        # Do nothing in the abstract class
        pass

    @abstractmethod
    def disconnect(self):
        """Called on bot exit. Should clean up connections."""
        # Do nothing in the abstract class
        pass

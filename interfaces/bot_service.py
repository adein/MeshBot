from abc import ABC, abstractmethod

class BotService(ABC):
    def __init__(self, event_bus, config):
        self.event_bus = event_bus
        self.config = config

    @abstractmethod
    def connect(self):
        """Called on bot startup. Should start any background threads/connections."""
        pass

    @abstractmethod
    def disconnect(self):
        """Called on bot exit. Should clean up connections."""
        pass

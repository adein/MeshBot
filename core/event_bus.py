import logging
from collections import defaultdict

class EventBus:
    def __init__(self):
        self.subscribers = defaultdict(list)
        self.logger = logging.getLogger("Core.EventBus")

    def subscribe(self, event_type, callback):
        """
        Modules call this to listen for specific events.
        callback: a function that accepts 'data'
        """
        self.subscribers[event_type].append(callback)
        self.logger.debug(f"Subscribed to {event_type}")

    def publish(self, event_type, data=None):
        """
        Services call this when something happens.
        """
        if event_type in self.subscribers:
            for callback in self.subscribers[event_type]:
                try:
                    callback(data)
                except Exception as e:
                    self.logger.error(f"Error in event handler for {event_type}: {e}")

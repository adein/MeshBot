import logging
from collections import defaultdict


class EventBus:
    """
    Simple Event Bus for inter-module communication.
    """

    def __init__(self):
        self.subscribers = defaultdict(list)
        self.logger = logging.getLogger("Core.EventBus")

    def subscribe(self, event_type: str, callback):
        """
        Modules call this to listen for specific events.

        :param event_type: The type of event to subscribe to.
        :type event_type: str
        :param callback: A function that accepts 'data'
        """
        self.subscribers[event_type].append(callback)
        self.logger.debug("Subscribed to %s", event_type)

    def publish(self, event_type: str, data=None):
        """
        Services call this when something happens.

        :param event_type: The type of event being published.
        :type event_type: str
        :param data: Optional data associated with the event.
        """
        if event_type in self.subscribers:
            for callback in self.subscribers[event_type]:
                try:
                    callback(data)
                except Exception as e:
                    self.logger.error(
                        "Error in event handler for %s: %s", event_type, e, exc_info=True)

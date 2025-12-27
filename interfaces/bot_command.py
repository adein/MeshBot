from abc import ABC

class BotCommand(ABC):
    # Default these to None so the IDE knows they exist
    trigger: str = None
    event_topic: str = None


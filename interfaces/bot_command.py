from abc import ABC


class BotCommand(ABC):
    """
    Abstract base class for bot commands.
    """
    trigger: str
    event_topic: str

from dataclasses import dataclass


@dataclass
class CommandStat:
    """
    Dataclass to hold command statistics.
    """
    __slots__ = ['command', 'count']
    command: str
    count: int


@dataclass
class UserStat:
    """
    Dataclass to hold user statistics.
    """
    __slots__ = ['node_id', 'channel', 'count']
    node_id: str
    channel: int
    count: int


@dataclass
class ChannelStat:
    """
    Dataclass to hold channel statistics.
    """
    __slots__ = ['channel', 'count']
    channel: int
    count: int

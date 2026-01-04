from dataclasses import dataclass


@dataclass
class CommandData:
    """
    Data class to hold command information.
    """
    __slots__ = ['sender_id', 'receiver_id', 'parameters', 'raw_message',
                 'channel', 'rx_time', 'rx_snr', 'hops_away', 'via_mqtt', 'is_dm']
    sender_id: str
    receiver_id: str
    parameters: list[str] | None
    raw_message: str
    channel: int | None
    rx_time: int
    rx_snr: float | None
    hops_away: int | None
    via_mqtt: bool
    is_dm: bool

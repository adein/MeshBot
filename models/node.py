from dataclasses import dataclass


@dataclass
class NodeInfo:
    """
    Dataclass to hold node information.
    """
    __slots__ = ['node_id', 'long_name', 'short_name', 'mac_address', 'hardware', 'role',
                 'public_key', 'unmessagable', 'latitude', 'longitude', 'altitude',
                 'snr', 'last_heard', 'channel', 'via_mqtt', 'hops_away', 'battery_level',
                 'channel_utilization', 'air_util_tx', 'uptime']
    node_id: str
    long_name: str | None
    short_name: str | None
    mac_address: str | None
    hardware: str | None
    role: str | None
    public_key: str | None
    unmessagable: bool | None
    latitude: float | None
    longitude: float | None
    altitude: int | None
    snr: float | None
    last_heard: int | None
    channel: int | None
    via_mqtt: bool | None
    hops_away: int | None
    battery_level: int | None
    channel_utilization: float | None
    air_util_tx: float | None
    uptime: int | None

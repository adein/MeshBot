from __future__ import annotations

import hashlib
import logging
import time
import threading

from dataclasses import dataclass
from typing import TYPE_CHECKING

from pubsub import pub

import meshtastic
import meshtastic.serial_interface
import meshtastic.tcp_interface

from core.database import Database, NodeInfo
from core.event_bus import EventBus
from interfaces.bot_service import BotService

if TYPE_CHECKING:
    from core.command_dispatcher import CommandData


CONNECTION_STATUS_TOPIC = "meshtastic_service.connection_status"
NODE_UPDATE_TOPIC = "meshtastic_service.node_update"
TEXT_MESSAGE_TOPIC = "meshtastic_service.text_message"


@dataclass
class TextPacket:
    """
    Represents a received text packet from Meshtastic.
    """
    __slots__ = ['packet_id', 'sender', 'receiver', 'sender_id', 'receiver_id', 'message', 'channel', 'rx_time', 'rx_snr', 'hop_limit',
                 'hop_start', 'next_hop', 'relay_node', 'want_ack', 'public_key', 'pki_encrypted', 'via_mqtt', 'is_dm', 'is_broadcast']
    packet_id: int
    sender: int
    receiver: int
    sender_id: str
    receiver_id: str | None
    message: str
    channel: int | None
    rx_time: int | None
    rx_snr: float | None
    hop_limit: int | None
    hop_start: int | None
    next_hop: int | None
    relay_node: int | None
    want_ack: bool | None
    public_key: str | None
    pki_encrypted: bool | None
    via_mqtt: bool | None
    is_dm: bool
    is_broadcast: bool


class MeshtasticService(BotService):
    """
    Service to interact with a Meshtastic node.
    """

    def __init__(self, event_bus: EventBus, db: Database, config, my_node_id: str):
        super().__init__(event_bus, config)
        self.db: Database = db
        self.my_node_id: str = my_node_id
        self.logger = logging.getLogger("Service.Meshtastic")
        self.connected = False
        self.running = False
        self.interface = None
        self.monitor_thread: threading.Thread | None = None
        # Format: {hash_string: timestamp}
        self.seen_messages: dict[str, float] = {}
        self.dedup_lock = threading.Lock()
        self.node_ip: str = self.config.get('node_ip')
        self.node_port: int = self.config.get('node_port')
        self.reconnect_base_delay: int = self.config.get(
            'reconnect_base_delay', 5)
        self.reconnect_max_delay: int = self.config.get(
            'reconnect_max_delay', 300)
        self.dedup_window: float = float(self.config.get('dedup_window', 5.0))
        # Subscribe to meshtastic library events
        pub.subscribe(self._on_connected, "meshtastic.connection.established")
        pub.subscribe(self._on_disconnected, "meshtastic.connection.lost")
        pub.subscribe(self._on_receive_node_update, "meshtastic.node_update")
        pub.subscribe(self._on_receive_position_packet,
                      "meshtastic.receive.position")
        pub.subscribe(self._on_receive_telemetry,
                      "meshtastic.receive.telemetry")
        pub.subscribe(self._on_receive_text_packet, "meshtastic.receive.text")
        pub.subscribe(self._on_receive_user_packet, "meshtastic.receive.user")

    def connect(self):
        """
        Starts the connection manager thread to connect to the Meshtastic node.
        """
        self.logger.info("Connecting...")
        self.running = True
        self.monitor_thread = threading.Thread(
            target=self._connection_manager, daemon=True)
        self.monitor_thread.start()

    def disconnect(self):
        """
        Closes the connection and stops the connection manager thread.
        """
        self.logger.info("Disconnecting...")
        self.running = False
        if self.interface:
            self.interface.close()
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)
        self.interface = None

    def _connection_manager(self):
        """
        The connection watchdog loop.
        Attempts to (re)connect with exponential backoff.
        """
        current_delay: int = self.reconnect_base_delay
        while self.running:
            try:
                self._connect_hardware()
                current_delay = self.reconnect_base_delay
                # Monitor loop (Blocks until connection is lost)
                self._watchdog_loop()

            except Exception as e:
                # Failure or disconnect
                self.logger.error("❌ Connection lost/failed: %s", e)
                if self.interface:
                    try:
                        self.interface.close()
                    except:
                        # Ignore
                        pass
                    self.interface = None
                # Backoff
                self.logger.info("Retrying in %d s...", current_delay)
                time.sleep(current_delay)
                current_delay = min(current_delay * 2,
                                    self.reconnect_max_delay)

    def _connect_hardware(self):
        """
        Initializes the library and registers callbacks.
        """
        self.logger.debug("Initializing hardware connection...")
        # TODO: Support auto choosing serial/tcp interface via config.yaml
        # self.interface = meshtastic.serial_interface.SerialInterface()
        self.interface = meshtastic.tcp_interface.TCPInterface(
            hostname=self.node_ip, portNumber=self.node_port)

    def _watchdog_loop(self):
        """
        Checks 'isConnected' periodically.
        """
        self.logger.debug("Monitoring connection status...")
        while self.running:
            if not self.interface.isConnected.is_set():
                raise ConnectionError("Hardware reported disconnect")
            # Sleep to save CPU
            time.sleep(2)

    def send_text(self, text: str, to_node_id: str | None = None, to_channel_number: int | None = None):
        """
        Sends a text message via Meshtastic.

        :param text: The text message to send
        :type text: str
        :param to_node_id: The destination node ID (if sending direct message)
        :type to_node_id: str | None
        :param to_channel_number: The destination channel number (if sending to a channel)
        :type to_channel_number: int | None
        """
        self.logger.debug("Send text message: %s to channel: %d, node: %s",
                          text, to_channel_number, to_node_id)
        if text is None or (to_node_id is None and to_channel_number is None):
            return
        if to_node_id is not None:
            self._send_text_to_node(text, to_node_id)
        elif to_channel_number is not None:
            self._send_text_to_channel(text, to_channel_number)

    def send_alert(self, text: str, to_node_id: str | None = None, to_channel_number: int | None = None):
        """
        Sends a text alert via Meshtastic.
        IMPORTANT NOTE: Alerts are very noisy and may bypass user settings on the device!
        Very similar to an "Amber Alert" on cell phones.

        :param text: The alert text to send
        :type text: str
        :param to_node_id: The destination node ID (if sending direct alert)
        :type to_node_id: str | None
        :param to_channel_number: The destination channel number (if sending to a channel)
        :type to_channel_number: int | None
        """
        self.logger.debug("Send text alert: %s to channel: %d, node: %s",
                          text, to_channel_number, to_node_id)
        if text is None or (to_node_id is None and to_channel_number is None):
            return
        if to_node_id is not None:
            self._send_alert_to_node(text, to_node_id)
        elif to_channel_number is not None:
            self._send_alert_to_channel(text, to_channel_number)

    def send_reply(self, reply: str, command_data: CommandData) -> bool:
        """
        Sends a reply to a command in the same manner as the original command (DM vs channel).

        :param reply: The reply text to send
        :type reply: str
        :param command_data: The original command data
        :type command_data: CommandData
        :return: True if the reply was sent, False otherwise
        :rtype: bool
        """
        if command_data.sender_id is not None and command_data.receiver_id == self.my_node_id:
            self.logger.debug("Send reply: %s, to node: %s",
                              reply, command_data.sender_id)
            self._send_text_to_node(reply, command_data.sender_id)
            return True
        elif command_data.channel is not None and command_data.receiver_id is None:
            self.logger.debug("Send reply: %s, to channel: %d",
                              reply, command_data.channel)
            self._send_text_to_channel(reply, command_data.channel)
            return True
        else:
            self.logger.warning(
                "Unable to send reply! Make sure your node ID is set correctly in config.")
        return False

    def _send_alert_to_channel(self, alert: str, channel: int):
        """
        Sends an alert to a channel, truncating if necessary to keep it to a single alert.

        :param alert: The alert to send
        :type alert: str
        :param channel: The channel number to send the alert to
        :type channel: int
        """
        alert_to_send = self._truncate_by_bytes(alert, 200)
        self.interface.sendAlert(text=alert_to_send, channelIndex=channel)

    def _send_alert_to_node(self, alert: str, node_id: str):
        """
        Sends an alert to a node, splitting the alert if necessary to keep each part within size limits.

        :param alert: The alert to send
        :type alert: str
        :param node_id: The destination node ID
        :type node_id: str
        """
        # Split the alert if necessary, sending up to 5 parts
        alert_chunks = self._split_text_by_bytes(alert, limit=200)[:5]
        for chunk in alert_chunks:
            self.interface.sendAlert(text=chunk, destinationId=node_id)

    def _send_text_to_channel(self, message: str, channel: int):
        """
        Sends a message to a channel, truncating if necessary to keep it to a single message.

        :param message: The message to send
        :type message: str
        :param channel: The channel number to send the message to
        :type channel: int
        """
        message_to_send = self._truncate_by_bytes(message, 200)
        self.interface.sendText(text=message_to_send, channelIndex=channel)

    def _send_text_to_node(self, message: str, node_id: str):
        """
        Sends a message to a node, splitting the message if necessary to keep each part within size limits.

        :param message: The message to send
        :type message: str
        :param node_id: The destination node ID
        :type node_id: str
        """
        # Split the message if necessary, sending up to 5 parts
        message_chunks = self._split_text_by_bytes(message, limit=200)[:5]
        for chunk in message_chunks:
            self.interface.sendText(text=chunk, destinationId=node_id)

    def _truncate_by_bytes(self, text, max_bytes):
        encoded = text.encode('utf-8')
        truncated_bytes = encoded[:max_bytes]
        return truncated_bytes.decode('utf-8', 'ignore')

    def _split_text_by_bytes(self, text, limit=200):
        chunks = []
        # Strict priority order: Newlines > Semicolons > Commas
        # Split on the first one of these types found in the chunk
        priority_delimiters = ["\n", ";", ","]
        while text:
            # Get the max safe chunk (hard limit)
            candidate = text[:limit]
            encoded = candidate.encode('utf-8')
            # Ensure we don't break multi-byte chars (emojis)
            sliced_encoded = encoded[:limit]
            valid_chunk = sliced_encoded.decode('utf-8', 'ignore')
            # If the valid_chunk takes the rest of the text, just take it all.
            if len(valid_chunk) == len(text):
                chunks.append(valid_chunk)
                break
            best_split_index = -1
            for delimiter in priority_delimiters:
                # Find the LAST occurrence of this specific delimiter
                idx = valid_chunk.rfind(delimiter)
                if idx != -1:
                    # We found a delimiter of this priority
                    # We accept this split immediately and stop looking for lower priority ones
                    best_split_index = idx
                    break
            if best_split_index != -1:
                # Split AFTER the delimiter (keep \n or , attached to the chunk)
                final_chunk = valid_chunk[:best_split_index + 1]
            else:
                # No delimiters found - Fall back to the hard byte cut
                final_chunk = valid_chunk
            chunks.append(final_chunk)
            text = text[len(final_chunk):]
        return chunks

    def _is_duplicate(self, msg_hash: str) -> bool:
        """
        Checks if the message hash exists and is recent.
        Also cleans up old cache entries to prevent memory leaks.
        """
        now = time.time()
        with self.dedup_lock:
            # Check if exists and is fresh
            if msg_hash in self.seen_messages:
                last_seen = self.seen_messages[msg_hash]
                if now - last_seen < self.dedup_window:
                    self.logger.debug(
                        "Message is a duplicate (seen %.2f s ago)", now - last_seen)
                    return True
            # Not a duplicate. Add to cache.
            self.seen_messages[msg_hash] = now
            # Cleanup (only runs occasionally to save CPU)
            if len(self.seen_messages) > 100:
                self._prune_cache(now)
            return False

    def _prune_cache(self, now):
        """Remove entries older than the window. MUST be called from within a lock."""
        self.logger.debug("Pruning deduplication cache...")
        to_remove = [k for k, v in self.seen_messages.items()
                     if now - v > self.dedup_window]
        for k in to_remove:
            del self.seen_messages[k]

    def _get_node_id(self, numeric_id: int | None = None, string_id: str | None = None) -> str | None:
        if string_id == '^all' or numeric_id == 4294967295:
            # Broadcast
            return None
        elif string_id and string_id.startswith('!'):
            return string_id
        elif numeric_id is not None:
            return f"!{numeric_id:x}"
        return None

    def _is_broadcast(self, numeric_id: int | None = None, string_id: str | None = None) -> bool:
        if string_id == '^all' or numeric_id == 4294967295:
            return True
        return False

    def _on_connected(self, interface, topic=pub.AUTO_TOPIC):
        # Called when we (re)connect to the radio
        self.connected = True
        self.logger.info("Connected.")
        self.event_bus.publish(CONNECTION_STATUS_TOPIC, True)

    def _on_disconnected(self, interface):
        # Called when we disconnect from the radio
        self.connected = False
        self.logger.info("Disconnected.")
        self.event_bus.publish(CONNECTION_STATUS_TOPIC, False)

    def _on_receive_node_update(self, node, interface):
        # Called when a node update arrives
        self.logger.debug("Received node update: %s ", node)
        user = node.get('user', {})
        node_id = self._get_node_id(
            numeric_id=node.get('num'), string_id=user.get('id'))
        if not node_id:
            self.logger.debug(
                "Unable to parse node update packet: missing node ID")
            return

        position = node.get('position', {})
        device_metrics = node.get('deviceMetrics', {})

        current_info: NodeInfo | None = self.db.get_node(node_id)
        if current_info is None:
            current_info = NodeInfo(node_id, None, None, None, None, None, None, None,
                                    None, None, None, None, None, None, None, None, None, None, None, None)

        current_info.long_name = user.get('longName', current_info.long_name)
        current_info.short_name = user.get(
            'shortName', current_info.short_name)
        current_info.mac_address = user.get(
            'macaddr', current_info.mac_address)
        current_info.hardware = user.get('hwModel', current_info.hardware)
        current_info.role = user.get('role', current_info.role)
        current_info.public_key = user.get(
            'publicKey', current_info.public_key)
        current_info.unmessagable = user.get(
            'isUnmessagable', current_info.unmessagable)

        current_info.altitude = position.get('altitude', current_info.altitude)
        current_info.latitude = position.get('latitude', current_info.latitude)
        current_info.longitude = position.get(
            'longitude', current_info.longitude)

        current_info.battery_level = device_metrics.get(
            'batteryLevel', current_info.battery_level)
        current_info.channel_utilization = device_metrics.get(
            'channelUtilization', current_info.channel_utilization)
        current_info.air_util_tx = device_metrics.get(
            'airUtilTx', current_info.air_util_tx)

        current_info.channel = node.get('channel', current_info.channel)

        last_heard = node.get('lastHeard')
        if last_heard and (not current_info.last_heard or last_heard > current_info.last_heard):
            current_info.last_heard = last_heard

        via_mqtt = node.get('viaMqtt')
        if via_mqtt is None:
            transport = node.get('transportMechanism')
            if transport:
                self.logger.debug(
                    "ViaMQTT not indicated, falling back to transport mechanism: %s", transport)
                via_mqtt = transport == "TRANSPORT_MQTT"
        if via_mqtt is not None:
            current_info.via_mqtt = via_mqtt

        if not via_mqtt:
            current_info.snr = node.get('snr', current_info.snr)
            current_info.hops_away = node.get(
                'hopsAway', current_info.hops_away)

        self.db.update_node(current_info)
        self.event_bus.publish(NODE_UPDATE_TOPIC, current_info)

    def _on_receive_telemetry(self, packet, interface):
        # Called when a telemetry packet arrives
        self.logger.debug("Received telemetry packet: %s", packet)
        node_id = self._get_node_id(numeric_id=packet.get(
            'from'), string_id=packet.get('fromId'))
        if not node_id:
            self.logger.debug(
                "Unable to parse telemetry packet: missing sender ID")
            return

        decoded = packet.get('decoded', {})
        telemetry = decoded.get('telemetry', {})
        device_metrics = telemetry.get('deviceMetrics', {})
        local_stats = telemetry.get('localStats', {})

        current_info = self.db.get_node(node_id)
        if current_info is None:
            current_info = NodeInfo(node_id, None, None, None, None, None, None, None,
                                    None, None, None, None, None, None, None, None, None, None, None, None)

        current_info.uptime = local_stats.get(
            'uptimeSeconds', current_info.uptime)
        current_info.channel_utilization = local_stats.get(
            'channelUtilization', current_info.channel_utilization)

        current_info.battery_level = device_metrics.get(
            'batteryLevel', current_info.battery_level)
        current_info.channel_utilization = device_metrics.get(
            'channelUtilization', current_info.channel_utilization)
        current_info.air_util_tx = device_metrics.get(
            'airUtilTx', current_info.air_util_tx)
        current_info.uptime = device_metrics.get(
            'uptimeSeconds', current_info.uptime)

        rx_time = packet.get('rxTime')
        if rx_time and (not current_info.last_heard or rx_time > current_info.last_heard):
            current_info.last_heard = rx_time

        self.db.update_node(current_info)
        self.event_bus.publish(NODE_UPDATE_TOPIC, current_info)

    def _on_receive_position_packet(self, packet, interface):
        # Called when a position packet arrives
        self.logger.debug("Received position packet: %s", packet)
        node_id = self._get_node_id(numeric_id=packet.get(
            'from'), string_id=packet.get('fromId'))
        if not node_id:
            self.logger.debug(
                "Unable to parse position packet: missing sender ID")
            return

        decoded = packet.get('decoded', {})
        position = decoded.get('position', {})

        current_info = self.db.get_node(node_id)
        if current_info is None:
            current_info = NodeInfo(node_id, None, None, None, None, None, None, None,
                                    None, None, None, None, None, None, None, None, None, None, None, None)

        current_info.altitude = position.get('altitude', current_info.altitude)
        current_info.latitude = position.get('latitude', current_info.latitude)
        current_info.longitude = position.get(
            'longitude', current_info.longitude)

        rx_time = packet.get('rxTime')
        if rx_time and (not current_info.last_heard or rx_time > current_info.last_heard):
            current_info.last_heard = rx_time

        via_mqtt = packet.get('viaMqtt')
        if via_mqtt is None:
            transport = packet.get('transportMechanism')
            if transport:
                self.logger.debug(
                    "ViaMQTT not indicated, falling back to transport mechanism: %s", transport)
                via_mqtt = transport == "TRANSPORT_MQTT"
        if via_mqtt is not None:
            current_info.via_mqtt = via_mqtt

        if not via_mqtt:
            current_info.snr = packet.get('rxSnr', current_info.snr)
            hop_limit = packet.get('hopLimit')
            hop_start = packet.get('hopStart')
            if hop_limit is not None and hop_start is not None:
                current_info.hops_away = hop_start - hop_limit

        self.db.update_node(current_info)
        self.event_bus.publish(NODE_UPDATE_TOPIC, current_info)

    def _on_receive_user_packet(self, packet, interface):
        # Called when a user packet arrives
        self.logger.debug("Received user packet: %s", packet)
        node_id = self._get_node_id(numeric_id=packet.get(
            'from'), string_id=packet.get('fromId'))
        if not node_id:
            self.logger.debug(
                "Unable to parse user packet: missing sender ID")
            return

        decoded = packet.get('decoded', {})
        user = decoded.get('user', {})

        current_info = self.db.get_node(node_id)
        if current_info is None:
            current_info = NodeInfo(node_id, None, None, None, None, None, None, None,
                                    None, None, None, None, None, None, None, None, None, None, None, None)

        current_info.long_name = user.get('longName', current_info.long_name)
        current_info.short_name = user.get(
            'shortName', current_info.short_name)
        current_info.mac_address = user.get(
            'macaddr', current_info.mac_address)
        current_info.hardware = user.get('hwModel', current_info.hardware)
        current_info.public_key = user.get(
            'publicKey', current_info.public_key)
        current_info.unmessagable = user.get(
            'isUnmessagable', current_info.unmessagable)

        rx_time = packet.get('rxTime')
        if rx_time and (not current_info.last_heard or rx_time > current_info.last_heard):
            current_info.last_heard = rx_time

        via_mqtt = packet.get('viaMqtt')
        if via_mqtt is None:
            transport = packet.get('transportMechanism')
            if transport:
                self.logger.debug(
                    "ViaMQTT not indicated, falling back to transport mechanism: %s", transport)
                via_mqtt = transport == "TRANSPORT_MQTT"
        if via_mqtt is not None:
            current_info.via_mqtt = via_mqtt

        if not via_mqtt:
            current_info.snr = packet.get('rxSnr', current_info.snr)
            hop_limit = packet.get('hopLimit')
            hop_start = packet.get('hopStart')
            if hop_limit is not None and hop_start is not None:
                current_info.hops_away = hop_start - hop_limit

        self.db.update_node(current_info)
        self.event_bus.publish(NODE_UPDATE_TOPIC, current_info)

    def _on_receive_text_packet(self, packet, interface):
        # Called when a text packet arrives
        self.logger.debug("Received text packet: %s", packet)
        decoded = packet.get('decoded', {})
        text = decoded.get('text')
        sender_id = self._get_node_id(numeric_id=packet.get(
            'from'), string_id=packet.get('fromId'))
        if not text or not sender_id:
            self.logger.debug(
                "Unable to parse text packet: missing sender ID or text")
            return

        # Determine if duplicate or not
        try:
            # Create a unique fingerprint for this message
            unique_str = f"{sender_id}:{text}"
            msg_hash = hashlib.md5(unique_str.encode('utf-8')).hexdigest()
            # Check for Duplicate
            if self._is_duplicate(msg_hash):
                self.logger.debug(
                    "♻️ Ignored duplicate message from %s", sender_id)
                return
        except Exception as e:
            self.logger.debug("Error parsing packet: %s", e, exc_info=True)

        # Process and update node info
        current_info = self.db.get_node(sender_id)
        if current_info is None:
            current_info = NodeInfo(sender_id, None, None, None, None, None, None, None,
                                    None, None, None, None, None, None, None, None, None, None, None, None)

        to_numeric = packet.get('to')
        to_id = packet.get('toId')
        receiver_id = self._get_node_id(numeric_id=to_numeric, string_id=to_id)
        is_broadcast = self._is_broadcast(
            numeric_id=to_numeric, string_id=to_id)

        current_info.public_key = packet.get(
            'publicKey', current_info.public_key)

        channel = packet.get('channel')
        if channel is None and is_broadcast:
            channel = 0  # Default public channel for broadcasts
        if channel is not None:
            current_info.channel = channel

        rx_time = packet.get('rxTime')
        if rx_time and (not current_info.last_heard or rx_time > current_info.last_heard):
            current_info.last_heard = rx_time

        via_mqtt = packet.get('viaMqtt')
        if via_mqtt is None:
            transport = packet.get('transportMechanism')
            if transport:
                self.logger.debug(
                    "ViaMQTT not indicated, falling back to transport mechanism: %s", transport)
                via_mqtt = transport == "TRANSPORT_MQTT"
        if via_mqtt is not None:
            current_info.via_mqtt = via_mqtt

        if not via_mqtt:
            current_info.snr = packet.get('rxSnr', current_info.snr)
            hop_limit = packet.get('hopLimit')
            hop_start = packet.get('hopStart')
            if hop_limit is not None and hop_start is not None:
                current_info.hops_away = hop_start - hop_limit

        self.db.update_node(current_info)

        # Log the message details for stats
        channel_log_value = packet.get('channel')
        if channel_log_value is None:
            if is_broadcast:
                channel_log_value = 0
            elif receiver_id is not None:
                channel_log_value = -1  # Magic number for DM
        if self.db:
            self.db.log_message(sender_id, channel_log_value)

        # Publish the text message event
        text_packet = TextPacket(
            packet_id=packet.get('id'),
            sender=packet.get('from'),
            receiver=packet.get('to'),
            sender_id=sender_id,
            receiver_id=receiver_id,
            message=text,
            channel=channel,
            rx_time=rx_time,
            rx_snr=packet.get('rxSnr'),
            hop_limit=packet.get('hopLimit'),
            hop_start=packet.get('hopStart'),
            next_hop=packet.get('nextHop'),
            relay_node=packet.get('relayNode'),
            want_ack=packet.get('wantAck'),
            public_key=packet.get('publicKey'),
            pki_encrypted=packet.get('pkiEncrypted'),
            via_mqtt=via_mqtt,
            is_dm=receiver_id is not None and not is_broadcast,
            is_broadcast=is_broadcast
        )
        self.event_bus.publish(TEXT_MESSAGE_TOPIC, text_packet)

import hashlib
import logging
import time
import threading
from dataclasses import dataclass
from pubsub import pub

import meshtastic
import meshtastic.serial_interface
import meshtastic.tcp_interface

from interfaces.bot_service import BotService
from core.database import NodeInfo


@dataclass
class TextPacket:
    __slots__ = ['packet_id', 'sender', 'receiver', 'sender_id', 'receiver_id', 'message', 'channel', 'rx_time', 'rx_snr',
                 'hop_limit', 'hop_start', 'next_hop', 'relay_node', 'want_ack', 'public_key', 'pki_encrypted', 'via_mqtt', 'is_dm']
    packet_id: int
    sender: int
    receiver: int
    sender_id: str
    receiver_id: str
    message: str
    channel: int
    rx_time: int
    rx_snr: float
    hop_limit: int
    hop_start: int
    next_hop: int
    relay_node: int
    want_ack: bool
    public_key: str
    pki_encrypted: bool
    via_mqtt: bool
    is_dm: bool


@dataclass
class TextToSend:
    __slots__ = ['text', 'to_node_id', 'to_channel_number', 'is_alert']
    text: str
    to_node_id: str | None
    to_channel_number: int | None
    is_alert: bool


class MeshtasticService(BotService):
    """
    Service to interact with the Meshtastic API.
    """

    def __init__(self, event_bus, db, config):
        super().__init__(event_bus, config)
        self.db = db
        self.logger = logging.getLogger("Service.Meshtastic")
        self.connected = False
        self.running = False
        self.interface = None
        self.monitor_thread = None
        self.seen_messages = {}  # Format: {hash_string: timestamp}
        self.dedup_lock = threading.Lock()
        self.node_ip = self.config.get('node_ip', 4403)
        self.node_port = self.config.get('node_port', "0.0.0.0")
        self.reconnect_base_delay = self.config.get('reconnect_base_delay', 5)
        self.reconnect_max_delay = self.config.get('reconnect_max_delay', 300)
        self.dedup_window = float(self.config.get('dedup_window', 5.0))
        self.logger.info("Node IP: %s", self.node_ip)
        self.logger.info("Node Port: %s", self.node_port)
        pub.subscribe(self._on_connected, "meshtastic.connection.established")
        pub.subscribe(self._on_disconnected, "meshtastic.connection.lost")
        pub.subscribe(self._on_receive_node_update, "meshtastic.node.updated")
        pub.subscribe(self._on_receive_position_packet,
                      "meshtastic.receive.position")
        pub.subscribe(self._on_receive_text_packet, "meshtastic.receive.text")
        pub.subscribe(self._on_receive_user_packet, "meshtastic.receive.user")
        self.event_bus.subscribe(
            "meshtastic_service.to_send", self._on_receive_text_to_send)

    def _on_connected(self, interface, topic=pub.AUTO_TOPIC):
        # Called when we (re)connect to the radio
        self.connected = True
        self.logger.info("Connected.")
        self.event_bus.publish("meshtastic.connection_status", True)

    def _on_disconnected(self, interface):
        # Called when we disconnect from the radio
        self.connected = False
        self.logger.info("Disconnected.")
        self.event_bus.publish("meshtastic.connection_status", False)

    def _on_receive_node_update(self, node, interface):
        # Called when a node update arrives
        self.logger.info("Received node update: %s ", node)
        node_id = None
        if 'user' in node and 'id' in node['user']:
            node_id = node['user']['id']
        if node_id is None or node_id == '':
            self.logger.warning("Node ID is missing in node packet!")
            return
        current_info = self.db.get_node(node_id)
        if current_info is None:
            current_info = NodeInfo(node_id, None, None, None, None, None,
                                    None, None, None, None, None, None, None, None, None, None)
        if 'user' in node:
            if 'longName' in node['user']:
                current_info.long_name = node['user']['longName']
            if 'shortName' in node['user']:
                current_info.short_name = node['user']['shortName']
            if 'macaddr' in node['user']:
                current_info.mac_address = node['user']['macaddr']
            if 'hwModel' in node['user']:
                current_info.hardware = node['user']['hwModel']
            if 'role' in node['user']:
                current_info.role = node['user']['role']
            if 'publicKey' in node['user']:
                current_info.public_key = node['user']['publicKey']
            if 'isUnmessagable' in node['user']:
                current_info.unmessagable = node['user']['isUnmessagable']
        if 'position' in node:
            if 'altitude' in node['position']:
                current_info.altitude = node['position']['altitude']
            if 'latitude' in node['position']:
                current_info.latitude = node['position']['latitude']
            if 'longitude' in node['position']:
                current_info.longitude = node['position']['longitude']
        if 'viaMqtt' in node:
            current_info.via_mqtt = node['viaMqtt']
        if 'snr' in node and ('viaMqtt' not in node or node['viaMqtt'] is False):
            current_info.snr = node['snr']
        if 'lastHeard' in node:
            current_info.last_heard = node['lastHeard']
        if 'channel' in node:
            current_info.channel = node['channel']
        if 'hopsAway' in node and ('viaMqtt' not in node or node['viaMqtt'] is False):
            current_info.hops_away = node['hopsAway']
        self.db.update_node(current_info)
        self.event_bus.publish("meshtastic.node_update", current_info)

    def _on_receive_position_packet(self, packet, interface):
        # Called when a position packet arrives
        self.logger.info("Received position packet: %s", packet)
        if "fromId" not in packet or "decoded" not in packet or "position" not in packet["decoded"]:
            self.logger.warning(
                "Unable to parse position packet: missing decoded or position fields")
            return
        node_id = None
        latitude = None
        longitude = None
        altitude = None
        rx_time = None
        rx_snr = None
        via_mqtt = None
        node_id = packet["fromId"]
        if node_id is None or node_id == '':
            self.logger.warning("Node ID is missing in position packet!")
            return
        if "transportMechanism" in packet:
            via_mqtt = packet['transportMechanism'] == "TRANSPORT_MQTT"
        if (via_mqtt is None or via_mqtt is False) and "rxSnr" in packet:
            rx_snr = packet["rxSnr"]
        position = packet["decoded"]["position"]
        if "altitude" in position:
            altitude = position["altitude"]
        if "latitude" in position:
            latitude = position["latitude"]
        if "longitude" in position:
            longitude = position["longitude"]
        if "rxTime" in position:
            rx_time = position["rxTime"]
        current_info = self.db.get_node(node_id)
        if current_info is None:
            current_info = NodeInfo(node_id, None, None, None, None, None,
                                    None, None, None, None, None, None, None, None, None, None)
        if altitude is not None:
            current_info.altitude = altitude
        if latitude is not None:
            current_info.latitude = latitude
        if longitude is not None:
            current_info.longitude = longitude
        if rx_time is not None:
            if current_info.last_heard is None or (rx_time > current_info.last_heard):
                current_info.last_heard = rx_time
        if rx_snr is not None:
            current_info.snr = rx_snr
        if via_mqtt is not None:
            current_info.via_mqtt = via_mqtt
        self.db.update_node(current_info)
        self.event_bus.publish("meshtastic.node_update", current_info)

    def _on_receive_user_packet(self, packet, interface):
        # Called when a user packet arrives
        self.logger.info("Received user packet: %s", packet)
        if "decoded" not in packet or "user" not in packet["decoded"] or "id" not in packet["decoded"]["user"]:
            self.logger.warning(
                "Unable to parse user packet: missing decoded or user fields")
            return
        node_id = None
        long_name = None
        short_name = None
        mac_address = None
        hardware = None
        public_key = None
        unmessagable = None
        rx_time = None
        rx_snr = None
        user = packet["decoded"]["user"]
        node_id = user["id"]
        if node_id is None or node_id == '':
            self.logger.warning("Node ID is missing in user packet!")
            return
        via_mqtt = True
        if "transportMechanism" in packet:
            via_mqtt = packet['transportMechanism'] == "TRANSPORT_MQTT"
        if (via_mqtt is None or via_mqtt is False) and "rxSnr" in packet:
            rx_snr = packet["rxSnr"]
        if "longName" in user:
            long_name = user["longName"]
        if "shortName" in user:
            short_name = user["shortName"]
        if "macaddr" in user:
            mac_address = user["macaddr"]
        if "hwModel" in user:
            hardware = user["hwModel"]
        if "publicKey" in user:
            public_key = user["publicKey"]
        if "isUnmessagable" in user:
            unmessagable = user["isUnmessagable"]
        if "rxTime" in packet:
            rx_time = packet["rxTime"]
        current_info = self.db.get_node(node_id)
        if current_info is None:
            current_info = NodeInfo(node_id, None, None, None, None, None,
                                    None, None, None, None, None, None, None, None, None, None)
        if long_name is not None:
            current_info.long_name = long_name
        if short_name is not None:
            current_info.short_name = short_name
        if mac_address is not None:
            current_info.mac_address = mac_address
        if hardware is not None:
            current_info.hardware = hardware
        if public_key is not None:
            current_info.public_key = public_key
        if unmessagable is not None:
            current_info.unmessagable = unmessagable
        if rx_snr is not None:
            current_info.snr = rx_snr
        if via_mqtt is not None:
            current_info.via_mqtt = via_mqtt
        if rx_time is not None:
            if current_info.last_heard is None or (rx_time > current_info.last_heard):
                current_info.last_heard = rx_time
        self.db.update_node(current_info)
        self.event_bus.publish("meshtastic.node_update", current_info)

    def _on_receive_text_packet(self, packet, interface):
        # Called when a text packet arrives
        self.logger.info("Received text packet: %s", packet)
        payload = packet.get('decoded', {})
        text = payload.get('text', '')
        sender_id = packet.get('fromId', '')
        receiver_id = packet.get('toId', '')
        try:
            if not text:
                self.logger.warning(
                    "Unable to parse text packet: missing decoded or text fields")
                return
            # Create a unique fingerprint for this message
            # We combine sender and text
            unique_str = f"{sender_id}:{text}"
            msg_hash = hashlib.md5(unique_str.encode('utf-8')).hexdigest()
            # Check for Duplicate
            if self._is_duplicate(msg_hash):
                self.logger.info(
                    "♻️ Ignored duplicate message from %s", sender_id)
                return
            # Message is not a duplicate
        except Exception as e:
            self.logger.error("Error parsing packet: %s", e, exc_info=True)

        channel_log_value = packet.get('channel', None)
        if channel_log_value is None:
            if receiver_id == '^all':
                channel_log_value = 0  # Default public channel
            elif receiver_id is not None:
                channel_log_value = -1  # Magic number for DM
        if self.db:
            self.db.log_message(sender_id, channel_log_value)

        channel = packet.get('channel', None)
        if channel is None and receiver_id == '^all':
            channel = 0

        packet_id = None
        sender = None
        receiver = None
        node_id = None
        message = None
        rx_time = None
        rx_snr = None
        hop_limit = None
        hop_start = None
        next_hop = None
        relay_node = None
        want_ack = None
        public_key = None
        pki_encrypted = None
        via_mqtt = None
        packet_id = packet["id"]
        sender = packet["from"]
        receiver = packet["to"]
        node_id = packet["fromId"]
        message = packet["decoded"]["text"]
        if "transportMechanism" in packet:
            via_mqtt = packet['transportMechanism'] == "TRANSPORT_MQTT"
        if "rxTime" in packet:
            rx_time = packet["rxTime"]
        if (via_mqtt is None or via_mqtt is False) and "rxSnr" in packet:
            rx_snr = packet["rxSnr"]
        if "hopLimit" in packet:
            hop_limit = packet["hopLimit"]
        if "hopStart" in packet:
            hop_start = packet["hopStart"]
        if "nextHop" in packet:
            next_hop = packet["nextHop"]
        if "relayNode" in packet:
            relay_node = packet["relayNode"]
        if "wantAck" in packet:
            want_ack = packet["wantAck"]
        if "publicKey" in packet:
            public_key = packet["publicKey"]
        if "pkiEncrypted" in packet:
            pki_encrypted = packet["pkiEncrypted"]
        text_packet = TextPacket(
            packet_id,
            sender,
            receiver,
            node_id,
            receiver_id,
            message,
            channel,
            rx_time,
            rx_snr,
            hop_limit,
            hop_start,
            next_hop,
            relay_node,
            want_ack,
            public_key,
            pki_encrypted,
            via_mqtt,
            receiver_id != '^all'
        )
        self.event_bus.publish("meshtastic.text_message", text_packet)
        if node_id is not None and node_id != '':
            current_info = self.db.get_node(node_id)
            if current_info is None:
                current_info = NodeInfo(node_id, None, None, None, None, None,
                                        None, None, None, None, None, None, None, None, None, None)
            if channel is not None:
                current_info.channel = channel
            if public_key is not None:
                current_info.public_key = public_key
            if via_mqtt is not None:
                current_info.via_mqtt = via_mqtt
            if rx_snr is not None:
                current_info.snr = rx_snr
            if rx_time is not None:
                if current_info.last_heard is None or (rx_time > current_info.last_heard):
                    current_info.last_heard = rx_time
            self.db.update_node(current_info)

    def _is_duplicate(self, msg_hash):
        """
        Checks if the hash exists and is recent.
        Also cleans up old cache entries to prevent memory leaks.
        """
        now = time.time()
        with self.dedup_lock:
            # Check if exists and is fresh
            if msg_hash in self.seen_messages:
                last_seen = self.seen_messages[msg_hash]
                if now - last_seen < self.dedup_window:
                    return True
            # Not a duplicate. Add to cache.
            self.seen_messages[msg_hash] = now
            # Cleanup (only runs occasionally to save CPU)
            if len(self.seen_messages) > 100:
                self._prune_cache(now)
            return False

    def _prune_cache(self, now):
        """Remove entries older than the window. MUST be called from within a lock."""
        to_remove = [k for k, v in self.seen_messages.items()
                     if now - v > self.dedup_window]
        for k in to_remove:
            del self.seen_messages[k]

    def _on_receive_text_to_send(self, data):
        # Called when a text message to send has been received internally from the event bus
        self.logger.info("Received a text message to send with data: %s", data)
        if not self.connected:
            self.logger.warning("Disconnected! Unable to send text message")
            return
        text = data.text
        to_node_id = data.to_node_id
        to_channel_number = data.to_channel_number
        is_alert = data.is_alert
        if is_alert is True:
            if to_node_id is not None:
                self.send_alert(text, to_node_id=to_node_id)
            elif to_channel_number is not None:
                self.send_alert(text, to_channel_number=to_channel_number)
            else:
                self.logger.warning("Unable to send message - missing data!")
        else:
            if to_node_id is not None:
                self.send_text(text, to_node_id=to_node_id)
            elif to_channel_number is not None:
                self.send_text(text, to_channel_number=to_channel_number)
            else:
                self.logger.warning("Unable to send message - missing data!")

    def connect(self):
        self.logger.info("Connecting...")
        self.running = True
        self.monitor_thread = threading.Thread(
            target=self._connection_manager, daemon=True)
        self.monitor_thread.start()

    def disconnect(self):
        self.logger.info("Disconnecting...")
        self.running = False
        if self.interface:
            self.interface.close()
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)
        self.interface = None

    def _connection_manager(self):
        """
        The main Watchdog loop.
        """
        current_delay = self.reconnect_base_delay
        while self.running:
            try:
                self._connect_hardware()
                # Success
                current_delay = self.reconnect_base_delay
                # Monitor Loop (Blocks until connection is lost)
                self._watchdog_loop()

            except Exception as e:
                # FAILURE or DISCONNECT
                self.logger.error("❌ Connection lost/failed: %s", e)
                # Ensure cleanup
                if self.interface:
                    try:
                        self.interface.close()
                    except:
                        # Ingore
                        pass
                    self.interface = None
                # Exponential Backoff
                self.logger.info("Retrying in %d s...", current_delay)
                time.sleep(current_delay)
                current_delay = min(current_delay * 2,
                                    self.reconnect_max_delay)

    def _connect_hardware(self):
        """
        Initializes the library and registers callbacks.
        """
        self.logger.info("Initializing hardware interface...")
        # TODO: Support auto choosing serial/tcp interface via config.yaml
        # self.interface = meshtastic.serial_interface.SerialInterface()
        self.interface = meshtastic.tcp_interface.TCPInterface(
            hostname=self.node_ip, portNumber=self.node_port)

    def _watchdog_loop(self):
        """
        Checks 'isConnected' periodically.
        The data handling happens automatically via callbacks in the background.
        """
        self.logger.info("Monitoring connection status...")
        while self.running:
            # Check the library's connection status
            if not self.interface.isConnected.is_set():
                raise ConnectionError("Hardware reported disconnect")
            # Sleep to save CPU
            time.sleep(2)

    def send_text(self, text, to_node_id=None, to_channel_number=None):
        self.logger.info("Send text message: %s to channel: %d, node: %s",
                         text, to_channel_number, to_node_id)
        if text is None or (to_node_id is None and to_channel_number is None):
            return None
        text_to_send = text[:200]
        if to_node_id is not None:
            return self.interface.sendText(text=text_to_send, destinationId=to_node_id)
        elif to_channel_number is not None:
            return self.interface.sendText(text=text_to_send, channelIndex=to_channel_number)
        return None

    def send_alert(self, text, to_node_id=None, to_channel_number=None):
        self.logger.info("Send text alert: %s to channel: %d, node: %s",
                         text, to_channel_number, to_node_id)
        if text is None or (to_node_id is None and to_channel_number is None):
            return None
        text_to_send = text[:200]
        if to_node_id is not None:
            return self.interface.sendAlert(text=text_to_send, destinationId=to_node_id)
        elif to_channel_number is not None:
            return self.interface.sendAlert(text=text_to_send, channelIndex=to_channel_number)
        return None

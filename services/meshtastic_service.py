import dataclasses
import hashlib
import logging
import time
import threading
import meshtastic
#import meshtastic.serial_interface
import meshtastic.tcp_interface

from dataclasses import dataclass
from pathlib import Path
from pubsub import pub

from interfaces.bot_service import BotService
from core.database import Database
from core.database import NodeInfo

@dataclass
class TextPacket:
    __slots__ = ['packet_id', 'sender', 'receiver', 'sender_id', 'receiver_id', 'message', 'channel', 'rx_time', 'rx_snr', 'hop_limit', 'hop_start', 'next_hop', 'relay_node', 'want_ack', 'public_key', 'pki_encrypted', 'via_mqtt', 'is_dm']
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
    to_node_id: str
    to_channel_number: int
    is_alert: bool

class MeshtasticService(BotService):
    """
    Service to interact with the Meshtastic API.
    """

    _node_info_storage = {}

    def __init__(self, event_bus, db, config):
        super().__init__(event_bus, config)
        self.db = db
        self.logger = logging.getLogger("Service.Meshtastic")
        self.connected = False
        self.running = False
        self.interface = None
        self.monitor_thread = None
        self.seen_messages = {} # Format: {hash_string: timestamp}
        self.dedup_lock = threading.Lock()
        self.NODE_IP = self.config.get('node_ip', 4403)
        self.NODE_PORT = self.config.get('node_port', "0.0.0.0")
        self.RECONNECT_BASE_DELAY = self.config.get('reconnect_base_delay', 5)
        self.RECONNECT_MAX_DELAY = self.config.get('reconnect_max_delay', 300)
        self.DEDUP_WINDOW = float(self.config.get('dedup_window', 5.0))
        self.logger.info(f"Node IP: {self.NODE_IP}")
        self.logger.info(f"Node Port: {self.NODE_PORT}")
        pub.subscribe(self._on_connected, "meshtastic.connection.established")
        pub.subscribe(self._on_disconnected, "meshtastic.connection.lost")
        pub.subscribe(self._on_receive_node_update, "meshtastic.node.updated")
        pub.subscribe(self._on_receive_position_packet, "meshtastic.receive.position")
        pub.subscribe(self._on_receive_text_packet, "meshtastic.receive.text")
        pub.subscribe(self._on_receive_user_packet, "meshtastic.receive.user")
        self.event_bus.subscribe("meshtastic_service.to_send", self._on_receive_text_to_send)

    def _on_connected(self, interface, topic=pub.AUTO_TOPIC):
        # Called when we (re)connect to the radio
        self.connected = True
        self.logger.info(f"Connected.")
        nodes_from_db = self.db.load_nodes()
        if nodes_from_db != None and len(nodes_from_db) > 0:
            self.logger.info(f"Read {len(nodes_from_db)} nodes from DB.")
            for existing_node in nodes_from_db.values():
                if existing_node.node_id != None and existing_node.node_id not in self._node_info_storage:
                    self._node_info_storage[existing_node.node_id] = existing_node
        self.logger.info(f"Node DB initialized with {len(self._node_info_storage)} nodes.")
        self.event_bus.publish("meshtastic.connection_status", True)

    def _on_disconnected(self, interface):
        # Called when we disconnect from the radio
        self.connected = False
        self.logger.info(f"Disconnected.")
        self._save_node_db()
        self.event_bus.publish("meshtastic.connection_status", False)

    def _on_receive_node_update(self, node, interface):
        # Called when a node update arrives
        self.logger.info(f"Received node update: {node}")
        node_id = None
        if 'user' in node and 'id' in node['user']:
            node_id = node['user']['id']
        if node_id == None or node_id == '':
            self.logger.warn(f"Node ID is missing in node packet!")
            return
        current_info = NodeInfo(None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None)
        if node_id in self._node_info_storage:
            current_info = self._node_info_storage[node_id]
            self.logger.info(f"Updating existing node info: {current_info}")
        current_info.node_id = node_id
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
        if 'snr' in node and ('viaMqtt' not in node or node['viaMqtt'] == False):
            current_info.snr = node['snr']
        if 'lastHeard' in node:
            current_info.last_heard = node['lastHeard']
        if 'channel' in node:
            current_info.channel = node['channel']
        if 'hopsAway' in node and ('viaMqtt' not in node or node['viaMqtt'] == False):
            current_info.hops_away = node['hopsAway']
        self.logger.info(f"Saving Node info: {current_info}")
        self._node_info_storage[node_id] = current_info
        self.event_bus.publish("meshtastic.node_update", current_info)

    def _on_receive_position_packet(self, packet, interface):
        # Called when a position packet arrives
        self.logger.info(f"Received position packet: {packet}")
        if "fromId" not in packet or "decoded" not in packet or "position" not in packet["decoded"]:
            self.logger.warn(f"Unable to parse position packet: missing decoded or position fields")
            return
        node_id = None
        latitude = None
        longitude = None
        altitude = None
        rx_time = None
        rx_snr = None
        via_mqtt = None
        node_id = packet["fromId"]
        if node_id == None or node_id == '':
            self.logger.warn(f"Node ID is missing in position packet!")
            return
        if "transportMechanism" in packet:
            via_mqtt = packet['transportMechanism'] == "TRANSPORT_MQTT"
        if (via_mqtt is None or via_mqtt == False) and "rxSnr" in packet:
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
        current_info = NodeInfo(None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None)
        if node_id in self._node_info_storage:
            current_info = self._node_info_storage[node_id]
            self.logger.info(f"Updating existing node info: {current_info}")
        current_info.node_id = node_id
        if altitude != None:
            current_info.altitude = altitude
        if latitude != None:
            current_info.latitude = latitude
        if longitude != None:
            current_info.longitude = longitude
        if rx_time != None:
            if current_info.last_heard is None or (rx_time > current_info.last_heard):
                current_info.last_heard = rx_time
        if rx_snr != None:
            current_info.snr = rx_snr
        if via_mqtt != None:
            current_info.via_mqtt = via_mqtt
        self.logger.info(f"Saving Node info: {current_info}")
        self._node_info_storage[node_id] = current_info
        self.event_bus.publish("meshtastic.node_update", current_info)

    def _on_receive_user_packet(self, packet, interface):
        # Called when a user packet arrives
        self.logger.info(f"Received user packet: {packet}")
        if "decoded" not in packet or "user" not in packet["decoded"] or "id" not in packet["decoded"]["user"]:
            self.logger.warn(f"Unable to parse user packet: missing decoded or user fields")
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
        if node_id == None or node_id == '':
            self.logger.warn(f"Node ID is missing in user packet!")
            return
        via_mqtt = True
        if "transportMechanism" in packet:
            via_mqtt = packet['transportMechanism'] == "TRANSPORT_MQTT"
        if (via_mqtt is None or via_mqtt == False) and "rxSnr" in packet:
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
        current_info = NodeInfo(None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None)
        if node_id in self._node_info_storage:
            current_info = self._node_info_storage[node_id]
            self.logger.info(f"Updating existing node info: {current_info}")
        current_info.node_id = node_id
        if long_name != None:
            current_info.long_name = long_name
        if short_name != None:
            current_info.short_name = short_name
        if mac_address != None:
            current_info.mac_address = mac_address
        if hardware != None:
            current_info.hardware = hardware
        if public_key != None:
            current_info.public_key = public_key
        if unmessagable != None:
            current_info.unmessagable = unmessagable
        if rx_snr != None:
            current_info.snr = rx_snr
        if via_mqtt != None:
            current_info.via_mqtt = via_mqtt
        if rx_time != None:
            if current_info.last_heard is None or (rx_time > current_info.last_heard):
                current_info.last_heard = rx_time
        self.logger.info(f"Saving Node info: {current_info}")
        self._node_info_storage[node_id] = current_info
        self.event_bus.publish("meshtastic.node_update", current_info)

    def _on_receive_text_packet(self, packet, interface):
        # Called when a text packet arrives
        self.logger.info(f"Received text packet: {packet}")
        payload = packet.get('decoded', {})
        text = payload.get('text', '')
        sender_id = packet.get('fromId', '')
        receiver_id = packet.get('toId', '')
        channel = packet.get('channel', None)
        try:
            if not text: 
                self.logger.warn(f"Unable to parse text packet: missing decoded or text fields")
                return
            # Create a unique fingerprint for this message
            # We combine sender and text
            unique_str = f"{sender_id}:{text}"
            msg_hash = hashlib.md5(unique_str.encode('utf-8')).hexdigest()
            # Check for Duplicate
            if self._is_duplicate(msg_hash):
                self.logger.info(f"♻️ Ignored duplicate message from {sender_id}: '{text}'")
                return
            # Message is not a duplicate
        except Exception as e:
            self.logger.error(f"Error parsing packet: {e}", exc_info=True)

        channel_log_value = packet.get('channel', -1)
        if receiver_id != '^all':
            channel_log_value = -1 # Magic number for DM
        if self.db:
            self.db.log_message(sender_id, channel_log_value)

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
        if (via_mqtt is None or via_mqtt == False) and "rxSnr" in packet:
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
        if node_id != None and node_id != '':
            current_info = NodeInfo(None, None, None, None, None, None, None, None, None, None, None, None, None, None, None, None)
            if node_id in self._node_info_storage:
                current_info = self._node_info_storage[node_id]
                self.logger.info(f"Updating existing node info: {current_info}")
            current_info.node_id = node_id
            if channel != None:
                current_info.channel = channel
            if public_key != None:
                current_info.public_key = public_key
            if via_mqtt != None:
                current_info.via_mqtt = via_mqtt
            if rx_snr != None:
                current_info.snr = rx_snr
            if rx_time != None:
                if current_info.last_heard is None or (rx_time > current_info.last_heard):
                    current_info.last_heard = rx_time
            self.logger.info(f"Saving Node info: {current_info}")
            self._node_info_storage[node_id] = current_info

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
                if now - last_seen < self.DEDUP_WINDOW:
                    return True
            # Not a duplicate. Add to cache.
            self.seen_messages[msg_hash] = now
            # Cleanup (only runs occasionally to save CPU)
            if len(self.seen_messages) > 100:
                self._prune_cache(now)
            return False

    def _prune_cache(self, now):
        """Remove entries older than the window. MUST be called from within a lock."""
        to_remove = [k for k, v in self.seen_messages.items() if now - v > self.DEDUP_WINDOW]
        for k in to_remove:
            del self.seen_messages[k]

    def _on_receive_text_to_send(self, data):
        # Called when a text message to send has been received internally from the event bus
        self.logger.info(f"Received a text message to send with data: {data}")
        if not self.connected:
            self.logger.warn(f"Disconnected! Unable to send text message")
            return
        text = data.text
        to_node_id = data.to_node_id
        to_channel_number = data.to_channel_number
        is_alert = data.is_alert
        if is_alert == True:
            if to_node_id != None:
                self.send_alert(text, to_node_id=to_node_id)
            elif to_channel_number != None:
                self.send_alert(text, to_channel_number=to_channel_number)
            else:
                self.logger.warn(f"Unable to send message - missing data!")
        else:
            if to_node_id != None:
                self.send_text(text, to_node_id=to_node_id)
            elif to_channel_number != None:
                self.send_text(text, to_channel_number=to_channel_number)
            else:
                self.logger.warn(f"Unable to send message - missing data!")

    def _save_node_db(self):
        self.logger.info(f"Saving {len(self._node_info_storage)} to DB.")
        self.db.update_nodes(self._node_info_storage)

    def connect(self):
        self.logger.info(f"Connecting...")
        self.running = True
        self.monitor_thread = threading.Thread(target=self._connection_manager, daemon=True)
        self.monitor_thread.start()

    def disconnect(self):
        self.logger.info(f"Disconnecting...")
        self.running = False
        self._save_node_db()
        if self.interface:
            self.interface.close()
        if self.monitor_thread:
            self.monitor_thread.join(timeout=2)
        self.interface = None


    def _connection_manager(self):
        """
        The main Watchdog loop.
        """
        current_delay = self.RECONNECT_BASE_DELAY
        while self.running:
            try:
                self._connect_hardware()
                # Success
                current_delay = self.RECONNECT_BASE_DELAY
                # Monitor Loop (Blocks until connection is lost)
                self._watchdog_loop()

            except Exception as e:
                # FAILURE or DISCONNECT
                self.logger.error(f"❌ Connection lost/failed: {e}")
                # Ensure cleanup
                if self.interface:
                    try:
                        self.interface.close()
                    except:
                        pass
                    self.interface = None
                # Exponential Backoff
                self.logger.info(f"Retrying in {current_delay}s...")
                time.sleep(current_delay)
                current_delay = min(current_delay * 2, self.RECONNECT_MAX_DELAY)

    def _connect_hardware(self):
        """
        Initializes the library and registers callbacks.
        """
        self.logger.info("Initializing hardware interface...")
        #self.interface = meshtastic.serial_interface.SerialInterface()
        self.interface = meshtastic.tcp_interface.TCPInterface(hostname=self.NODE_IP, portNumber=self.NODE_PORT)

    def _watchdog_loop(self):
        """
        Checks 'isConnected' periodically.
        The data handling happens automatically via callbacks in the background.
        """
        self.logger.info(f"Monitoring connection status...")
        while self.running:
            # Check the library's connection status
            if not self.interface.isConnected.is_set():
                raise ConnectionError("Hardware reported disconnect")
            # Sleep to save CPU
            time.sleep(2)

    def get_node_info(self, node_id):
        self.logger.info(f"Get node info for {node_id} ...")
        if node_id not in self._node_info_storage:
            return None
        node_info = self._node_info_storage[node_id]
        node_info_copy = dataclasses.replace(node_info)
        return node_info_copy

    def send_text(self, text, to_node_id=None, to_channel_number=None):
        self.logger.info(f"Send text message: {text} to channel: {to_channel_number}, node:{to_node_id}")
        if text == None or (to_node_id == None and to_channel_number == None):
            return None
        text_to_send = text[:200]
        if to_node_id != None:
            return self.interface.sendText(text=text_to_send, destinationId=to_node_id)
        elif to_channel_number != None:
            return self.interface.sendText(text=text_to_send, channelIndex=to_channel_number)
        return None

    def send_alert(self, text, to_node_id=None, to_channel_number=None):
        self.logger.info(f"Send text alert: {text} to channel: {to_channel_number}, node:{to_node_id}")
        if text == None or (to_node_id == None and to_channel_number == None):
            return None
        text_to_send = text[:200]
        if to_node_id != None:
            return self.interface.sendAlert(text=text_to_send, destinationId=to_node_id)
        elif to_channel_number != None:
            return self.interface.sendAlert(text=text_to_send, channelIndex=to_channel_number)
        return None

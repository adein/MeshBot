import logging
import sqlite3
import threading

from dataclasses import dataclass, asdict

from core.event_bus import EventBus


@dataclass
class NodeInfo:
    """
    Dataclass to hold node information.
    """
    __slots__ = ['node_id', 'long_name', 'short_name', 'mac_address', 'hardware', 'role',
                 'public_key', 'unmessagable', 'latitude', 'longitude', 'altitude',
                 'snr', 'last_heard', 'channel', 'via_mqtt', 'hops_away']
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


class Database:
    """
    Database service for the bot.
    Stores node details and command/message statistics.
    """

    def __init__(self, event_bus: EventBus, config):
        self.event_bus: EventBus = event_bus
        self.config = config
        self.logger = logging.getLogger("Service.Database")
        self.db_path: str = self.config.get('db_path', "bot_data.db")
        self.conn: sqlite3.Connection | None = None
        self.db_lock: threading.Lock = threading.Lock()

    def connect(self):
        """
        Establishes the database connection and configures it.
        Creates tables if needed.
        """
        self.conn = sqlite3.connect(
            self.db_path, check_same_thread=False, timeout=30.0)
        try:
            self.conn.execute("PRAGMA journal_mode=WAL;")
            self.conn.execute("PRAGMA synchronous=NORMAL;")
            self.conn.row_factory = sqlite3.Row
        except Exception as e:
            self.logger.error("Failed to configure DB: %s", e, exc_info=True)
        self._create_tables()
        self.logger.debug("Database opened.")

    def disconnect(self):
        """
        Closes the database connection.
        """
        if self.conn:
            with self.db_lock:
                self.conn.close()
        self.logger.debug("Database closed.")

    def _create_tables(self):
        self.logger.debug("Creating initial database tables...")
        with self.db_lock:
            cursor = self.conn.cursor()
            cursor.execute('''
            CREATE TABLE IF NOT EXISTS nodes (
                node_id TEXT PRIMARY KEY,
                long_name TEXT, short_name TEXT, mac_address TEXT,
                hardware TEXT, role TEXT, public_key TEXT,
                unmessagable BOOLEAN, latitude REAL, longitude REAL,
                altitude INTEGER, snr REAL, last_heard INTEGER,
                channel INTEGER, via_mqtt BOOLEAN, hops_away INTEGER
            )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS command_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    command TEXT,
                    user_id TEXT
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS message_stats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    user_id TEXT,
                    channel INTEGER DEFAULT 0
                )
            ''')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS system_state (
                    key TEXT PRIMARY KEY,
                    value TEXT
                )
            ''')
            self.conn.commit()

    def get_state(self, key: str, default: str | None = None) -> str | None:
        """
        Retrieves a value from the system_state table.

        :param key: The key to look up in the system_state table.
        :type key: str
        :param default: The default value to return if the key is not found.
        :type default: str | None
        :return: The value associated with the key, or the default if not found.
        :rtype: str | None
        """
        try:
            with self.db_lock:
                with self.conn:
                    cursor = self.conn.execute(
                        "SELECT value FROM system_state WHERE key=?", (key,))
                    row = cursor.fetchone()
                    return row[0] if row else default
        except Exception as e:
            self.logger.error(f"Failed to get state {key}: {e}")
            return default

    def set_state(self, key: str, value: str):
        """
        Saves a value to the system_state table.

        :param key: The key to store in the system_state table.
        :type key: str
        :param value: The value to associate with the key.
        :type value: str
        """
        try:
            with self.db_lock:
                with self.conn:
                    self.conn.execute(
                        "INSERT OR REPLACE INTO system_state (key, value) VALUES (?, ?)",
                        (key, str(value))
                    )
        except Exception as e:
            self.logger.error(f"Failed to set state {key}: {e}")

    def log_command(self, command_name: str, user_id: str):
        """
        Logs a command usage.

        :param command_name: The command that was used.
        :type command_name: str
        :param user_id: The (node) ID of the user who issued the command.
        :type user_id: str
        """
        self.logger.debug(
            "Logging command usage: %s by user %s", command_name, user_id)
        try:
            with self.db_lock:
                with self.conn:
                    self.conn.execute(
                        "INSERT INTO command_stats (command, user_id) VALUES (?, ?)",
                        (command_name, user_id)
                    )
        except Exception as e:
            self.logger.error("Failed to log command: %s", e, exc_info=True)

    def log_message(self, user_id: str, channel_number: int):
        """
        Logs a message sent by a user.

        :param user_id: The (node) ID of the user who sent the message.
        :type user_id: str
        :param channel_number: The channel number where the message was sent.
        :type channel_number: int
        """
        self.logger.debug(
            "Logging message from user %s on channel %d", user_id, channel_number)
        try:
            with self.db_lock:
                with self.conn:
                    self.conn.execute(
                        "INSERT INTO message_stats (user_id, channel) VALUES (?, ?)",
                        (user_id, channel_number)
                    )
        except Exception as e:
            self.logger.error("Failed to log message: %s", e, exc_info=True)

    def update_node(self, node_info: NodeInfo):
        """
        Updates (or creates) a single node record immediately.

        :param node_info: The node details to store.
        :type node_info: NodeInfo
        """
        self.logger.info("Updating information for node: %s",
                         node_info.node_id)
        self.logger.debug("Updating node information: %s", node_info)
        try:
            # Convert Dataclass to Dictionary
            # This ensures we have all keys: node_id, long_name, etc.
            data = asdict(node_info)

            with self.db_lock:
                with self.conn:
                    self.conn.execute('''
                        INSERT OR REPLACE INTO nodes (
                            node_id, long_name, short_name, mac_address,
                            hardware, role, public_key, unmessagable,
                            latitude, longitude, altitude, snr,
                            last_heard, channel, via_mqtt, hops_away
                        )
                        VALUES (
                            :node_id, :long_name, :short_name, :mac_address,
                            :hardware, :role, :public_key, :unmessagable,
                            :latitude, :longitude, :altitude, :snr,
                            :last_heard, :channel, :via_mqtt, :hops_away
                        )
                    ''', data)

        except Exception as e:
            nid = getattr(node_info, 'node_id', 'UNKNOWN')
            self.logger.error("Failed to update node %s: %s",
                              nid, e, exc_info=True)

    def get_node(self, node_id: str) -> NodeInfo | None:
        """
        Retrieves details of a single node by ID.

        :param node_id: The ID of the node to retrieve.
        :type node_id: str
        :return: The NodeInfo if found, else None.
        :rtype: NodeInfo | None
        """
        self.logger.debug("Retrieving node information for: %s", node_id)
        temp_conn = sqlite3.connect(self.db_path, timeout=10.0)
        try:
            temp_conn.row_factory = sqlite3.Row
            cursor = temp_conn.execute(
                "SELECT * FROM nodes WHERE node_id = ?", (node_id,))
            row = cursor.fetchone()
            if row:
                ni = NodeInfo(**dict(row))
                self.logger.debug("Found node information %s", node_id)
                return ni
            return None
        except Exception as e:
            self.logger.error("Failed to get node %s: %s",
                              node_id, e, exc_info=True)
            return None
        finally:
            temp_conn.close()

    def get_top_commands(self, limit: int = 5) -> list[CommandStat]:
        """
        Returns the most used commands.

        :param limit: Number of top commands to return.
        :type limit: int
        :return: List of CommandStat
        :rtype: list[CommandStat]
        """
        self.logger.debug("Retrieving top %d commands", limit)
        temp_conn = sqlite3.connect(self.db_path, timeout=10.0)
        try:
            temp_conn.row_factory = sqlite3.Row
            cursor = temp_conn.cursor()
            cursor.execute('''
                SELECT command, COUNT(*) as count 
                FROM command_stats 
                GROUP BY command 
                ORDER BY count DESC 
                LIMIT ?
            ''', (limit,))
            rows = cursor.fetchall()
            return [CommandStat(command=row['command'], count=row['count']) for row in rows]
        finally:
            temp_conn.close()

    def get_top_talkers(self, limit: int = 5) -> list[UserStat]:
        """
        Returns the most active users by message count.

        :param limit: Number of top talkers to return.
        :type limit: int
        :return: List of UserStat
        :rtype: list[UserStat]
        """
        self.logger.debug("Retrieving top %d talkers", limit)
        temp_conn = sqlite3.connect(self.db_path, timeout=10.0)
        try:
            temp_conn.row_factory = sqlite3.Row
            cursor = temp_conn.cursor()
            cursor.execute('''
                SELECT user_id, channel, COUNT(*) as count 
                FROM message_stats 
                GROUP BY user_id, channel 
                ORDER BY count DESC 
                LIMIT ?
            ''', (limit,))
            rows = cursor.fetchall()
            return [UserStat(node_id=row['user_id'], channel=row['channel'], count=row['count']) for row in rows]
        finally:
            temp_conn.close()

    def get_channel_usage(self) -> list[ChannelStat]:
        """
        Returns the total messages per channel.
        EXCLUDES Direct Messages (channel -1).

        :return: List of ChannelStat
        :rtype: list[ChannelStat]
        """
        self.logger.debug("Retrieving channel usage")
        temp_conn = sqlite3.connect(self.db_path, timeout=10.0)
        try:
            temp_conn.row_factory = sqlite3.Row
            cursor = temp_conn.cursor()
            cursor.execute('''
                SELECT channel, COUNT(*) as count 
                FROM message_stats 
                WHERE channel >= 0  -- <--- Exclude DMs
                GROUP BY channel 
                ORDER BY count DESC
            ''')
            rows = cursor.fetchall()
            return [ChannelStat(channel=row['channel'], count=row['count']) for row in rows]
        finally:
            temp_conn.close()

    def search_nodes(self, query_text: str, limit: int = 3) -> list[NodeInfo]:
        """
        Searches for nodes matching the query string.

        :param query_text: The text to search for in long_name, short_name, node_id, or hardware.
        :type query_text: str
        :param limit: Number of results to return.
        :type limit: int
        :return: List of NodeInfo
        :rtype: list[NodeInfo]
        """
        self.logger.debug("Searching nodes with query: %s", query_text)
        temp_conn = sqlite3.connect(self.db_path, timeout=10.0)
        try:
            temp_conn.row_factory = sqlite3.Row
            cursor = temp_conn.cursor()
            clean_text = query_text.strip().lower()
            wildcard_query = f"%{clean_text}%"
            cursor.execute('''
                SELECT node_id, long_name, short_name, mac_address, hardware, role, public_key, latitude, longitude, altitude, snr, via_mqtt, channel, hops_away, last_heard, unmessagable
                FROM nodes 
                WHERE lower(long_name) LIKE ? 
                   OR lower(short_name) LIKE ? 
                   OR lower(node_id) LIKE ?
                   OR lower(hardware) LIKE ?
                LIMIT ?
            ''', (wildcard_query, wildcard_query, wildcard_query, wildcard_query, limit,))
            rows = cursor.fetchall()
            return [NodeInfo(
                node_id=row['node_id'],
                long_name=row['long_name'],
                short_name=row['short_name'],
                mac_address=row['mac_address'],
                hardware=row['hardware'],
                role=row['role'],
                public_key=row['public_key'],
                latitude=row['latitude'],
                longitude=row['longitude'],
                altitude=row['altitude'],
                snr=row['snr'],
                via_mqtt=row['via_mqtt'],
                channel=row['channel'],
                hops_away=row['hops_away'],
                last_heard=row['last_heard'],
                unmessagable=row['unmessagable']
            ) for row in rows]
        except Exception as e:
            self.logger.error("Node search failed: %s", e, exc_info=True)
            return []
        finally:
            temp_conn.close()

    def get_nodes_near(self, lat: float, lon: float, radius_miles: int = 20) -> list[NodeInfo]:
        """
        Searches for nodes within roughly `radius_miles` of a point.

        :param lat: The latitude of the center point.
        :type lat: float
        :param lon: The longitude of the center point.
        :type lon: float
        :param radius_miles: The radius in miles to search within.
        :type radius_miles: int
        :return: List of NodeInfo 
        :rtype: list[NodeInfo]
        """
        # Calculate Bounding Box (approximation for speed and simplicity)
        # 1 degree lat ~= 69 miles
        # 1 degree lon ~= 69 miles * cos(lat)
        lat_change = radius_miles / 69.0
        lon_change = radius_miles / 50.0  # Estimate for US latitudes
        min_lat = lat - lat_change
        max_lat = lat + lat_change
        min_lon = lon - lon_change
        max_lon = lon + lon_change
        self.logger.debug(
            "Searching nodes near lat: %f, lon: %f, radius: %d miles", lat, lon, radius_miles)
        temp_conn = sqlite3.connect(self.db_path, timeout=10.0)
        try:
            temp_conn.row_factory = sqlite3.Row
            cursor = temp_conn.cursor()
            cursor.execute('''
                SELECT node_id, long_name, short_name, mac_address, hardware, role, public_key, latitude, longitude, altitude, snr, via_mqtt, channel, hops_away, last_heard, unmessagable
                FROM nodes
                WHERE latitude BETWEEN ? AND ?
                    AND longitude BETWEEN ? AND ?
            ''', (min_lat, max_lat, min_lon, max_lon))
            rows = cursor.fetchall()
            return [NodeInfo(
                node_id=row['node_id'],
                long_name=row['long_name'],
                short_name=row['short_name'],
                mac_address=row['mac_address'],
                hardware=row['hardware'],
                role=row['role'],
                public_key=row['public_key'],
                latitude=row['latitude'],
                longitude=row['longitude'],
                altitude=row['altitude'],
                snr=row['snr'],
                via_mqtt=row['via_mqtt'],
                channel=row['channel'],
                hops_away=row['hops_away'],
                last_heard=row['last_heard'],
                unmessagable=row['unmessagable']
            ) for row in rows]
        except Exception as e:
            self.logger.error("Geo-search failed: %s", e, exc_info=True)
            return []
        finally:
            temp_conn.close()

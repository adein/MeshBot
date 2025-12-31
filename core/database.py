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
        self.logger.info("Database connected.")

    def disconnect(self):
        """
        Closes the database connection.
        """
        if self.conn:
            with self.db_lock:
                self.conn.close()
            self.logger.info("Database closed.")

    def _create_tables(self):
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
            self.conn.commit()

    def log_command(self, command_name: str, user_id: str):
        """
        Logs a command usage.

        :param command_name: The command that was used.
        :type command_name: str
        :param user_id: The (node) ID of the user who issued the command.
        :type user_id: str
        """
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
        temp_conn = sqlite3.connect(self.db_path, timeout=10.0)
        try:
            temp_conn.row_factory = sqlite3.Row
            cursor = temp_conn.execute(
                "SELECT * FROM nodes WHERE node_id = ?", (node_id))
            row = cursor.fetchone()
            if row:
                return NodeInfo(**dict(row))
            return None
        except Exception as e:
            self.logger.error("Failed to get node %s: %s",
                              node_id, e, exc_info=True)
            return None
        finally:
            temp_conn.close()

    def get_top_commands(self, limit: int = 5) -> list[sqlite3.Row]:
        """
        Returns the most used commands.

        :param limit: Number of top commands to return.
        :type limit: int
        :return: List of rows containing (command, count).
        :rtype: list[Row]
        """
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
            return cursor.fetchall()
        finally:
            temp_conn.close()

    def get_top_talkers(self, limit: int = 5) -> list[sqlite3.Row]:
        """
        Returns the most active users by message count.

        :param limit: Number of top talkers to return.
        :type limit: int
        :return: List of rows containing (node_id, channel, count).
        :rtype: list[Row]
        """
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
            return cursor.fetchall()
        finally:
            temp_conn.close()

    def get_channel_usage(self) -> list[sqlite3.Row]:
        """
        Returns the total messages per channel.
        EXCLUDES Direct Messages (channel -1).

        :return: List of rows containing (channel, count).
        :rtype: list[Row]
        """
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
            return cursor.fetchall()
        finally:
            temp_conn.close()

    def search_nodes(self, query_text: str, limit: int = 3) -> list[sqlite3.Row]:
        """
        Searches for nodes matching the query string.

        :param query_text: The text to search for in long_name, short_name, node_id, or hardware.
        :type query_text: str
        :param limit: Number of results to return.
        :type limit: int
        :return: List of rows containing node information.
        :rtype: list[Row]
        """
        temp_conn = sqlite3.connect(self.db_path, timeout=10.0)
        try:
            temp_conn.row_factory = sqlite3.Row
            cursor = temp_conn.cursor()
            clean_text = query_text.strip().lower()
            wildcard_query = f"%{clean_text}%"
            self.logger.info("Searching for nodes matching: %s", clean_text)
            cursor.execute('''
                SELECT node_id, long_name, short_name, hardware, role, latitude, longitude, altitude, snr, via_mqtt, channel, hops_away, last_heard, unmessagable
                FROM nodes 
                WHERE lower(long_name) LIKE ? 
                   OR lower(short_name) LIKE ? 
                   OR lower(node_id) LIKE ?
                   OR lower(hardware) LIKE ?
                LIMIT ?
            ''', (wildcard_query, wildcard_query, wildcard_query, wildcard_query, limit))
            return cursor.fetchall()
        except Exception as e:
            self.logger.error("Search failed: %s", e, exc_info=True)
            return []
        finally:
            temp_conn.close()

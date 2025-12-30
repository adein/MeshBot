import logging
import sqlite3

from dataclasses import dataclass, asdict, fields

@dataclass
class NodeInfo:
    __slots__ = ['node_id', 'long_name', 'short_name', 'mac_address', 'hardware', 'role', 
                 'public_key', 'unmessagable', 'latitude', 'longitude', 'altitude', 
                 'snr', 'last_heard', 'channel', 'via_mqtt', 'hops_away']
    node_id: str
    long_name: str
    short_name: str
    mac_address: str
    hardware: str
    role: str
    public_key: str
    unmessagable: bool
    latitude: float
    longitude: float
    altitude: int
    snr: float
    last_heard: int
    channel: int
    via_mqtt: bool
    hops_away: int


class Database:
    def __init__(self, event_bus, config):
        self.event_bus = event_bus
        self.config = config
        self.logger = logging.getLogger("Service.Database")
        self.DB_PATH = self.config.get('db_path', "bot_data.db")
        self.conn = None

    def connect(self):
        self.conn = sqlite3.connect(self.DB_PATH, check_same_thread=False)
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA synchronous=NORMAL;")
        self.conn.row_factory = sqlite3.Row 
        self._create_tables()
        self.logger.info("Database connected.")

    def disconnect(self):
        if self.conn:
            self.conn.close()
            self.logger.info("Database closed.")

    def _create_tables(self):
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

    def log_command(self, command_name, user_id):
        try:
            with self.conn:
                self.conn.execute(
                    "INSERT INTO command_stats (command, user_id) VALUES (?, ?)",
                    (command_name, user_id)
                )
        except Exception as e:
            self.logger.error(f"Failed to log command: {e}", exc_info=True)

    def log_message(self, user_id, channel_number):
        try:
            with self.conn:
                self.conn.execute(
                    "INSERT INTO message_stats (user_id, channel) VALUES (?, ?)", 
                    (user_id, channel_number)
                )
        except Exception as e:
            self.logger.error(f"Failed to log message: {e}", exc_info=True)

    def update_nodes(self, node_dict):
        """Saves a dictionary of {id: NodeInfo} to the DB."""
        self.logger.info(f"Attempting to save {len(node_dict)} nodes to DB...")
        if not node_dict:
            self.logger.warn(f"Node dictionary is None")
            return
        # Extract the data into the list of tuples you provided
        data_tuples = [tuple(getattr(node, field) for field in NodeInfo.__slots__) 
                       for node in node_dict.values()]
        try:
            # Use a context manager to ensure the transaction is committed to disk
            with self.conn:
                query = f"""
                INSERT OR REPLACE INTO nodes ({', '.join(NodeInfo.__slots__)})
                VALUES ({', '.join(['?'] * len(NodeInfo.__slots__))})
                """
                self.conn.executemany(query, data_tuples)
            # This only runs if the 'with' block finishes successfully
            self.logger.info(f"Successfully saved {len(data_tuples)} nodes.")
        except sqlite3.Error as e:
            self.logger.error(f"SQLite error: {e}", exc_info=True)

    def load_nodes(self):
        """Loads all nodes from the DB into a dictionary."""
        cursor = self.conn.execute("SELECT * FROM nodes")
        rows = cursor.fetchall()
        # Use dictionary unpacking to recreate the dataclass instances
        return {row['node_id']: NodeInfo(**dict(row)) for row in rows}

    def get_top_commands(self, limit=5):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT command, COUNT(*) as count 
            FROM command_stats 
            GROUP BY command 
            ORDER BY count DESC 
            LIMIT ?
        ''', (limit,))
        return cursor.fetchall()

    def get_top_talkers(self, limit=5):
        """Returns (User ID, Channel, Count)"""
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT user_id, channel, COUNT(*) as count 
            FROM message_stats 
            GROUP BY user_id, channel 
            ORDER BY count DESC 
            LIMIT ?
        ''', (limit,))
        return cursor.fetchall()

    def get_channel_usage(self):
        """
        Returns total volume per channel.
        EXCLUDES Direct Messages (channel -1).
        """
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT channel, COUNT(*) as count 
            FROM message_stats 
            WHERE channel >= 0  -- <--- Exclude DMs
            GROUP BY channel 
            ORDER BY count DESC
        ''')
        return cursor.fetchall()

    def search_nodes(self, query_text):
        """
        Searches nodes table for matching long_name, short_name, or node_id.
        Returns a list of tuples, limited to 20 results.
        """
        cursor = self.conn.cursor()
        clean_text = query_text.strip().lower()
        wildcard_query = f"%{clean_text}%"
        
        try:
            cursor.execute('''
                SELECT node_id, long_name, short_name, hardware, role, latitude, longitude, altitude, snr, via_mqtt, channel, hops_away, last_heard, unmessagable
                FROM nodes 
                WHERE lower(long_name) LIKE ? 
                   OR lower(short_name) LIKE ? 
                   OR lower(node_id) LIKE ?
                LIMIT 20
            ''', (wildcard_query, wildcard_query, wildcard_query))
            return cursor.fetchall()
        except Exception as e:
            self.logger.error(f"Search failed: {e}", exc_info=True)
            return []
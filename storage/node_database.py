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

class NodeDatabase:
    def __init__(self, db_path="./nodes.db"):
        self.logger = logging.getLogger("Storage.NodeDatabase")
        self.conn = sqlite3.connect(db_path, check_same_thread=False) # ok, since we don't write often/in parallel
        self.conn.execute("PRAGMA journal_mode=WAL;")
        self.conn.execute("PRAGMA synchronous=NORMAL;")
        # Allows accessing rows by name: row['node_id']
        self.conn.row_factory = sqlite3.Row 
        self._create_table()

    def _create_table(self):
        query = """
        CREATE TABLE IF NOT EXISTS nodes (
            node_id TEXT PRIMARY KEY,
            long_name TEXT, short_name TEXT, mac_address TEXT,
            hardware TEXT, role TEXT, public_key TEXT,
            unmessagable BOOLEAN, latitude REAL, longitude REAL,
            altitude INTEGER, snr REAL, last_heard INTEGER,
            channel INTEGER, via_mqtt BOOLEAN, hops_away INTEGER
        )
        """
        self.conn.execute(query)
        self.conn.commit()

    def save_nodes(self, node_dict):
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
            self.logger.error(f"SQLite error: {e}")

    def load_nodes(self):
        """Loads all nodes from the DB into a dictionary."""
        cursor = self.conn.execute("SELECT * FROM nodes")
        rows = cursor.fetchall()
        
        # Use dictionary unpacking to recreate the dataclass instances
        return {row['node_id']: NodeInfo(**dict(row)) for row in rows}

    def close(self):
        self.conn.close()

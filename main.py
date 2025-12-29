# main.py updates
import logging
import yaml
import sys
from core.command_dispatcher import CommandDispatcher
from core.database import Database
from core.event_bus import EventBus
from core.plugin_manager import PluginManager
from core.scheduler import BotScheduler
from services.meshtastic_service import MeshtasticService
from ui.dashboard import BotDashboard
from ui.log_handler import TextualLogHandler

def load_config():
    try:
        with open("config.yaml", "r") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print("config.yaml not found. Exiting.")
        sys.exit(1)

if __name__ == "__main__":
    # Load Config
    config = load_config()
    logging.basicConfig(
        level=getattr(logging, config['core'].get('log_level', 'INFO')),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        filename='bot_activity.log',
        filemode='w'
    )
    my_node_id = config['core'].get('my_node_id', 'ERROR')

    # Initialize Global Components
    event_bus = EventBus()
    db = Database(event_bus, config.get('core', {}).get('database', {}))
    meshtastic_service = MeshtasticService(event_bus, db, config.get('services', {}).get('meshtastic_service', {}))
    global_services = {
        "bus": event_bus,
        "db": db,
        "mesh": meshtastic_service 
    }
    # Connect
    db.connect()
    meshtastic_service.connect()

    # Initialize Core Components
    plugin_mgr = PluginManager(
        modules_dir="./modules",
        config=config,
        global_services=global_services,
        my_node=my_node_id,
    )
    scheduler = BotScheduler(plugin_manager=plugin_mgr)
    dispatcher = CommandDispatcher(global_services, commands_dir="./commands", my_node=my_node_id)
    dispatcher.load_commands()
    dispatcher.start()

    # Load & Start
    plugin_mgr.discover_and_load()
    scheduler.reload_jobs()
    scheduler.start()

    # Start Dashboard UI
    app = BotDashboard(plugin_mgr, scheduler, event_bus)
    try:
        app.run() # This blocks and takes over the terminal
    except KeyboardInterrupt:
        print("\nForce closing...")
    finally:
        root = logging.getLogger()
        for handler in root.handlers[:]:
            if isinstance(handler, TextualLogHandler):
                root.removeHandler(handler)
        scheduler.stop()
        meshtastic_service.disconnect()

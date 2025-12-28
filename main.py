# main.py updates
import logging
import yaml
import sys
from core.command_dispatcher import CommandDispatcher
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

    # Initialize Core Components
    event_bus = EventBus()
    meshtastic_service = MeshtasticService(event_bus, config.get('services', {}).get('meshtastic_service', {}))
    plugin_mgr = PluginManager(
        modules_dir="./modules",
        config=config,
        event_bus=event_bus,
        my_node=my_node_id,
        mesh_svc=meshtastic_service
    )
    scheduler = BotScheduler(plugin_manager=plugin_mgr)
    dispatcher = CommandDispatcher(event_bus, commands_dir="./commands", my_node=my_node_id)
    dispatcher.load_commands()
    dispatcher.start()

    meshtastic_service.connect()

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

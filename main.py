# main.py updates
import logging
import yaml
import cmd
import threading
import sys
from core.command_dispatcher import CommandDispatcher
from core.event_bus import EventBus
from core.plugin_manager import PluginManager
from core.scheduler import BotScheduler
from services.meshtastic_service import MeshtasticService

def load_config():
    try:
        with open("config.yaml", "r") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        print("config.yaml not found. Exiting.")
        sys.exit(1)

# Setup Logging
config = load_config()
logging.basicConfig(
    level=getattr(logging, config['core'].get('log_level', 'INFO')),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    filename='bot_activity.log' 
)
my_node_id = config['core'].get('my_node_id', 'ERROR')

class BotShell(cmd.Cmd):
    intro = 'Welcome to the MeshBot admin console. Type help or ? to list commands.\n'
    prompt = '> '

    def __init__(self, plugin_mgr, scheduler):
        super().__init__()
        self.plugin_mgr = plugin_mgr
        self.scheduler = scheduler

    def do_status(self, arg):
        """Show status of all loaded modules."""
        modules = self.plugin_mgr.get_all_modules()
        print("\n--- Module Status ---")
        if not modules:
            print("No modules loaded.")
        for name, mod in modules.items():
            state = "ENABLED" if mod.is_enabled() else "DISABLED"
            print(f"[{state}] {name}")
        print("---------------------\n")

    def do_toggle(self, arg):
        """Toggle a module on or off. Usage: toggle sample_task"""
        mod = self.plugin_mgr.get_module(arg)
        if mod:
            # Flip the boolean
            current = mod.config.get('enabled', False)
            mod.config['enabled'] = not current
            print(f"{arg} is now {'ENABLED' if mod.config['enabled'] else 'DISABLED'}.")
            
            # Re-register jobs immediately to reflect the change
            self.scheduler.reload_jobs()
        else:
            print(f"Module '{arg}' not found.")

    def do_reload(self, arg):
        """Reloads configuration and plugins."""
        print("Reloading system...")
        
        # 1. Reload Config
        new_config = load_config()
        self.plugin_mgr.config = new_config
        
        # 2. Rediscover Plugins (in case new files were added)
        self.plugin_mgr.discover_and_load()
        
        # 3. Restart Scheduler Jobs
        self.scheduler.reload_jobs()
        print("System reloaded.")

    def do_exit(self, arg):
        """Stop the bot and exit."""
        print("Stopping scheduler...")
        self.scheduler.stop()
        return True

if __name__ == "__main__":
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

    # Start CLI
    try:
        # Pass the instances to the shell so it can control them
        shell = BotShell(plugin_mgr, scheduler)
        shell.cmdloop()
    except KeyboardInterrupt:
        print("\nForce closing...")
    finally:
        scheduler.stop()
        meshtastic_service.disconnect()


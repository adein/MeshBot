import logging
from datetime import datetime

import yaml
from rich.table import Table
from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import Header, Footer, Input, RichLog
from textual import events, on

from core.event_bus import EventBus
from core.plugin_manager import PluginManager
from core.scheduler import BotScheduler
from models.node import NodeInfo
from models.statistics import CommandStat, UserStat, ChannelStat
from ui.log_handler import TextualLogHandler
from utils.geo_utils import get_city_state_offline, get_lat_lon_from_string, calculate_distance
from utils.time_utils import duration_to_str


class BotDashboard(App):
    """Textual-based TUI Dashboard for MeshBot."""

    CSS = """
    Screen {
        layout: vertical;
    }

    /* Wrapper for the two log windows */
    #main_container {
        height: 1fr;
        layout: vertical;
        margin-bottom: 1; /* Safety buffer */
    }

    /* (1/3rd of the container) */
    #system_log {
        height: 1fr;
        border: solid red;
    }

    /* (2/3rds of the container) */
    #console_output {
        height: 2fr;
        border: solid green;
    }

    /* Input Bar */
    #command_input {
        height: 3;
        border: wide white;
    }
    """

    def __init__(self, plugin_mgr: PluginManager, scheduler: BotScheduler, event_bus: EventBus):
        super().__init__()
        self.plugin_mgr: PluginManager = plugin_mgr
        self.scheduler: BotScheduler = scheduler
        self.event_bus: EventBus = event_bus
        self.console_output: RichLog = RichLog(
            highlight=True, markup=True, max_lines=1000, id="console_output")
        self.system_log: RichLog = RichLog(
            highlight=True, markup=True, max_lines=1000, id="system_log")
        self.command_history: list[str] = []
        self.history_index: int = 0
        config = self._load_config()
        core_config = config.get('core', {})
        channels_config = core_config.get('channels', {})
        self.channel_names = {
            0: channels_config.get('channel_0_name', 'LongFast'),
            1: channels_config.get('channel_1_name', '1'),
            2: channels_config.get('channel_2_name', '2'),
            3: channels_config.get('channel_3_name', '3'),
            4: channels_config.get('channel_4_name', '4'),
            5: channels_config.get('channel_5_name', '5'),
            6: channels_config.get('channel_6_name', '6'),
            7: channels_config.get('channel_7_name', '7'),
        }

    def _load_config(self):
        try:
            with open("config.yaml", "r") as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            logging.error("config.yaml not found!")
            self.console_output.write("[bold red]config.yaml not found!")
            self.exit()

    def compose(self) -> ComposeResult:
        """Create the UI layout."""
        yield Header(show_clock=True)

        # This container holds the split view
        yield Container(
            RichLog(id="system_log", markup=True, max_lines=1000),
            RichLog(id="console_output", markup=True, max_lines=1000),
            id="main_container"
        )

        yield Input(placeholder="Type a command...", id="command_input")
        yield Footer()

    def on_mount(self):
        """Called when the app starts. Setup logging hook."""
        # Capture the Widgets
        self.system_log = self.query_one("#system_log", RichLog)
        self.console_output = self.query_one("#console_output", RichLog)

        # Config & Logging Setup
        config = self.plugin_mgr.config
        log_cfg = config.get('logging', {})

        file_lvl_str = log_cfg.get('file_level', 'DEBUG').upper()
        ui_lvl_str = log_cfg.get('ui_level', 'INFO').upper()
        log_filename = log_cfg.get('log_file', 'bot_activity.log')

        file_level = getattr(logging, file_lvl_str, logging.DEBUG)
        ui_level = getattr(logging, ui_lvl_str, logging.INFO)

        # Setup Root Logger
        root_logger = logging.getLogger()
        root_logger.setLevel(min(file_level, ui_level))
        root_logger.handlers.clear()

        # File Handler
        try:
            file_handler = logging.FileHandler(log_filename, mode='a')
            file_handler.setLevel(file_level)
            file_fmt = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            file_handler.setFormatter(file_fmt)
            root_logger.addHandler(file_handler)
        except Exception as e:
            self.console_output.write(f"[red]Failed to setup log file: {e}[/]")

        # UI Handler (System Log)
        ui_handler = TextualLogHandler(self.system_log)
        ui_handler.setLevel(ui_level)
        ui_fmt = logging.Formatter('%(asctime)s - %(message)s')
        ui_handler.setFormatter(ui_fmt)
        root_logger.addHandler(ui_handler)

        # Silence Noise
        logging.getLogger("asyncio").setLevel(logging.WARNING)
        logging.getLogger("urllib3").setLevel(logging.WARNING)

        self.console_output.write(
            f"[bold yellow]Logging Initialized (File: {file_lvl_str}, UI: {ui_lvl_str}).[/]")
        self.console_output.write(
            "[bold green]Welcome to the MeshBot admin console. Type help or ? to list commands.[/]")
        self.query_one("#command_input").focus()

    @on(Input.Submitted, "#command_input")
    def handle_input(self, event: Input.Submitted):
        """Runs when user presses Enter."""
        command: str = event.value.strip()
        self.query_one("#command_input").value = ""  # Clear input

        if not command:
            return

        if not self.command_history or self.command_history[-1] != command:
            self.command_history.append(command)
        self.history_index = len(self.command_history)

        self.console_output.write(f"[bold]> {command}[/]")
        self.process_command(command)

    def on_key(self, event: events.Key):
        """Intercept Up/Down arrows for history navigation."""
        input_widget = self.query_one("#command_input")
        if not input_widget.has_focus:
            return
        if event.key == "up":
            if self.history_index > 0:
                self.history_index -= 1
                input_widget.value = self.command_history[self.history_index]
                input_widget.cursor_position = len(input_widget.value)
            event.stop()
        elif event.key == "down":
            if self.history_index < len(self.command_history):
                self.history_index += 1
                if self.history_index == len(self.command_history):
                    input_widget.value = ""
                else:
                    input_widget.value = self.command_history[self.history_index]
                    input_widget.cursor_position = len(input_widget.value)
            event.stop()

    def process_command(self, cmd_text: str):
        """
        Process a command entered by the administrator.

        :param cmd_text: The full command text entered.
        :type cmd_text: str
        """
        parts = cmd_text.split()
        base = parts[0].lower().removeprefix("!")
        args = parts[1:] if len(parts) > 1 else None

        if base == "exit":
            self.exit()

        elif base == "help" or base == "?":
            self.console_output.write("[bold]Available Commands:[/]")
            self.console_output.write("  [cyan]exit[/]: Exit the bot.")
            self.console_output.write(
                "  [cyan]help or ?[/]: Show this help message.")
            self.console_output.write(
                "  [cyan]directnodes[/]: List nodes with zero hops between us and them.")
            self.console_output.write(
                "  [cyan]highnodes[/]: List nodes with the highest reported altitude.")
            self.console_output.write(
                "  [cyan]neighbornodes[/]: List most recenly heard non-MQTT nodes.")
            self.console_output.write(
                "  [cyan]nodesearch[/]: Search the node database.")
            self.console_output.write(
                "  [cyan]rolesearch[/]: Search the node database for specific roles.")
            self.console_output.write(
                "  [cyan]reload[/]: Reload configuration and modules.")
            self.console_output.write(
                "  [cyan]stats[/]: Show bot and mesh stats.")
            self.console_output.write(
                "  [cyan]status[/]: Show status of all modules.")
            self.console_output.write(
                "  [cyan]toggle <module_name>[/]: Enable/Disable a module.")

        elif base == "directnodes":
            self._direct_nodes(args)

        elif base == "highnodes":
            self._high_nodes(args)

        elif base == "neighbornodes":
            self._neighbor_nodes(args)

        elif base == "nodesearch":
            self._node_search_command(args)

        elif base == "rolesearch":
            self._role_search_command(args)

        elif base == "reload":
            self.console_output.write("Reloading modules...")
            # Reload Config
            new_config = self._load_config()
            self.plugin_mgr.config = new_config
            # Rediscover Plugins (in case new files were added)
            self.plugin_mgr.discover_and_load()
            # Restart Scheduler Jobs
            self.scheduler.reload_jobs()
            self.console_output.write("System reloaded.")

        elif base == "stats":
            self._stats_command(args)

        elif base == "status":
            self.console_output.write("--- STATUS REPORT ---")
            for name, mod in self.plugin_mgr.get_all_modules().items():
                status = "[green]ENABLED[/]" if mod.is_enabled() else "[red]DISABLED[/]"
                self.console_output.write(f"{status} {name}")
            self.console_output.write("---------------------")

        elif base == "toggle" and args:
            module_name = args[0]
            mod = self.plugin_mgr.get_module(module_name)
            if mod:
                mod.config['enabled'] = not mod.config['enabled']
                state = "Enabled" if mod.config['enabled'] else "Disabled"
                self.console_output.write(
                    f"Module {module_name} is now {state}")
                self.scheduler.reload_jobs()
            else:
                self.console_output.write(
                    f"[bold red]Module {module_name} not found.[/]")

        else:
            self.console_output.write(f"[yellow]Unknown command: {base}[/]")

    def _get_channel_name(self, channel_id: int) -> str:
        if channel_id == -1:
            return "DM w/ Bot"
        return self.channel_names.get(channel_id, str(channel_id))

    def _node_search_command(self, command_arguments):
        if not command_arguments:
            self.console_output.write(
                "[red]Usage: nodesearch <name OR node_id OR city, state>[/]")
            return

        # Access the DB Service via the Plugin Manager's registry
        db = self.plugin_mgr.services.get('db')
        if not db:
            self.console_output.write(
                "[bold red]Error: Database Service not loaded.[/]")
            return

        clean_args = ' '.join(command_arguments)
        is_location_search = False
        target_lat, target_lon = None, None
        if "," in clean_args or clean_args.lower().startswith("near "):
            search_term = clean_args.replace("near ", "")
            self.console_output.write(
                f"Geocoding [bold cyan]'{search_term}'[/]...")
            coords = get_lat_lon_from_string(search_term)
            if coords:
                target_lat, target_lon = coords
                is_location_search = True
                self.console_output.write(
                    f"Searching 10mi radius around {coords}...")
            else:
                self.console_output.write(
                    "[yellow]Could not find that location. Trying name search...[/]")

        if is_location_search:
            # Geo Search
            raw_results: list[NodeInfo] = db.get_nodes_near(
                target_lat, target_lon, radius_miles=10)
            # Sort by Distance (Closest first)
            temp_results = []
            for node in raw_results:
                dist = calculate_distance(
                    target_lat, target_lon, node.latitude, node.longitude)
                if dist <= 10:
                    # Append distance to the tuple for display
                    temp_results.append((node, dist))
            temp_results.sort(key=lambda x: x[-1])
            results = [t[0] for t in temp_results]
        else:
            # Standard Text Search
            self.console_output.write(
                f"Searching for: [bold cyan]'{clean_args}'[/]...")
            results: list[NodeInfo] = db.search_nodes(clean_args, limit=20)

        if not results:
            self.console_output.write(
                "[yellow]No matching nodes found.[/]")
        else:
            # Create a pretty table
            table = Table(title=f"Search Results ({len(results)})")
            table.add_column("Node ID", style="cyan")
            table.add_column("Long Name", style="green")
            table.add_column("Short", style="magenta")
            table.add_column("Hardware", style="white")
            table.add_column("Role", style="blue")
            table.add_column("Location", style="red")
            table.add_column("Altitude", style="pink1")
            table.add_column("Unmessagable", style="violet")
            table.add_column("Hops", style="orange1")
            table.add_column("Channel", style="sky_blue2")
            table.add_column("SNR", style="yellow")
            table.add_column("Ch Util", style="purple3")
            table.add_column("Battery", style="light_green")
            table.add_column("Uptime", style="orchid")
            table.add_column("MQTT", style="purple")
            table.add_column("Seen", style="grey53")

            for node in results:
                # Handle potential None values safely
                node_id = str(node.node_id or "???")
                long_name = str(node.long_name or "Unknown")
                short_name = str(node.short_name or "Unknown")
                hw_model = str(node.hardware or "Unknown")
                role = str(node.role or "Unknown")
                lat = node.latitude
                lon = node.longitude
                altitude = str(
                    node.altitude) if node.altitude is not None else "N/A"
                snr = str(node.snr) if node.snr is not None else "N/A"
                raw_mqtt = node.via_mqtt
                channel = str(
                    node.channel) if node.channel is not None else "N/A"
                channel_util = str(
                    node.channel_utilization) if node.channel_utilization is not None else "Unknown"
                hops = str(
                    node.hops_away) if node.hops_away is not None else "N/A"
                battery = str(
                    node.battery_level) if node.battery_level is not None else "N/A"
                uptime = duration_to_str(
                    node.uptime) if node.uptime is not None else "Unknown"
                raw_last_seen = node.last_heard
                raw_unmessagable = node.unmessagable

                if lat and lon:
                    location_str = get_city_state_offline(lat, lon)
                else:
                    location_str = "N/A"
                if raw_mqtt == 1:
                    mqtt = "True"
                else:
                    mqtt = "False"
                if raw_last_seen:
                    dt = datetime.fromtimestamp(float(raw_last_seen))
                    last_seen_str = dt.strftime("%Y-%m-%d %H:%M")
                else:
                    last_seen_str = "Never"
                if raw_unmessagable == 1:
                    unmessagable = "True"
                else:
                    unmessagable = "False"

                table.add_row(node_id, long_name, short_name, hw_model, role, location_str, altitude,
                              unmessagable, hops, channel, snr, channel_util, battery, uptime, mqtt, last_seen_str)

            # Render the table to the console window
            self.console_output.write(table)

    def _role_search_command(self, command_arguments):
        if not command_arguments:
            self.console_output.write(
                "[red]Usage: rolesearch <role>[/]")
            return

        # Access the DB Service via the Plugin Manager's registry
        db = self.plugin_mgr.services.get('db')
        if not db:
            self.console_output.write(
                "[bold red]Error: Database Service not loaded.[/]")
            return

        clean_args = ' '.join(command_arguments)
        self.console_output.write(
            f"Searching for: [bold cyan]'{clean_args}'[/]...")
        results: list[NodeInfo] = db.search_roles(clean_args, limit=20)

        if not results:
            self.console_output.write(
                "[yellow]No matching nodes found.[/]")
        else:
            # Create a pretty table
            table = Table(title=f"Search Results ({len(results)})")
            table.add_column("Node ID", style="cyan")
            table.add_column("Long Name", style="green")
            table.add_column("Short", style="magenta")
            table.add_column("Hardware", style="white")
            table.add_column("Role", style="blue")
            table.add_column("Location", style="red")
            table.add_column("Altitude", style="pink1")
            table.add_column("Unmessagable", style="violet")
            table.add_column("Hops", style="orange1")
            table.add_column("Channel", style="sky_blue2")
            table.add_column("SNR", style="yellow")
            table.add_column("Ch Util", style="purple3")
            table.add_column("Battery", style="light_green")
            table.add_column("Uptime", style="orchid")
            table.add_column("MQTT", style="purple")
            table.add_column("Seen", style="grey53")

            for node in results:
                # Handle potential None values safely
                node_id = str(node.node_id or "???")
                long_name = str(node.long_name or "Unknown")
                short_name = str(node.short_name or "Unknown")
                hw_model = str(node.hardware or "Unknown")
                role = str(node.role or "Unknown")
                lat = node.latitude
                lon = node.longitude
                altitude = str(
                    node.altitude) if node.altitude is not None else "N/A"
                snr = str(node.snr) if node.snr is not None else "N/A"
                raw_mqtt = node.via_mqtt
                channel = str(
                    node.channel) if node.channel is not None else "N/A"
                channel_util = str(
                    node.channel_utilization) if node.channel_utilization is not None else "Unknown"
                hops = str(
                    node.hops_away) if node.hops_away is not None else "N/A"
                battery = str(
                    node.battery_level) if node.battery_level is not None else "N/A"
                uptime = duration_to_str(
                    node.uptime) if node.uptime is not None else "Unknown"
                raw_last_seen = node.last_heard
                raw_unmessagable = node.unmessagable

                if lat and lon:
                    location_str = get_city_state_offline(lat, lon)
                else:
                    location_str = "N/A"
                if raw_mqtt == 1:
                    mqtt = "True"
                else:
                    mqtt = "False"
                if raw_last_seen:
                    dt = datetime.fromtimestamp(float(raw_last_seen))
                    last_seen_str = dt.strftime("%Y-%m-%d %H:%M")
                else:
                    last_seen_str = "Never"
                if raw_unmessagable == 1:
                    unmessagable = "True"
                else:
                    unmessagable = "False"

                table.add_row(node_id, long_name, short_name, hw_model, role, location_str, altitude,
                              unmessagable, hops, channel, snr, channel_util, battery, uptime, mqtt, last_seen_str)

            # Render the table to the console window
            self.console_output.write(table)

    def _high_nodes(self, command_arguments):
        # Access the DB Service via the Plugin Manager's registry
        db = self.plugin_mgr.services.get('db')
        if not db:
            self.console_output.write(
                "[bold red]Error: Database Service not loaded.[/]")
            return

        results: list[NodeInfo] = db.get_top_nodes_by_altitude(limit=20)

        if not results:
            self.console_output.write(
                "[yellow]No results.[/]")
        else:
            # Create a pretty table
            table = Table(title=f"Search Results ({len(results)})")
            table.add_column("Node ID", style="cyan")
            table.add_column("Long Name", style="green")
            table.add_column("Short", style="magenta")
            table.add_column("Hardware", style="white")
            table.add_column("Role", style="blue")
            table.add_column("Location", style="red")
            table.add_column("Altitude", style="pink1")
            table.add_column("Unmessagable", style="violet")
            table.add_column("Hops", style="orange1")
            table.add_column("Channel", style="sky_blue2")
            table.add_column("SNR", style="yellow")
            table.add_column("Ch Util", style="purple3")
            table.add_column("Battery", style="light_green")
            table.add_column("Uptime", style="orchid")
            table.add_column("MQTT", style="purple")
            table.add_column("Seen", style="grey53")

            for node in results:
                # Handle potential None values safely
                node_id = str(node.node_id or "???")
                long_name = str(node.long_name or "Unknown")
                short_name = str(node.short_name or "Unknown")
                hw_model = str(node.hardware or "Unknown")
                role = str(node.role or "Unknown")
                lat = node.latitude
                lon = node.longitude
                altitude = str(
                    node.altitude) if node.altitude is not None else "N/A"
                snr = str(node.snr) if node.snr is not None else "N/A"
                raw_mqtt = node.via_mqtt
                channel = str(
                    node.channel) if node.channel is not None else "N/A"
                channel_util = str(
                    node.channel_utilization) if node.channel_utilization is not None else "Unknown"
                hops = str(
                    node.hops_away) if node.hops_away is not None else "N/A"
                battery = str(
                    node.battery_level) if node.battery_level is not None else "N/A"
                uptime = duration_to_str(
                    node.uptime) if node.uptime is not None else "Unknown"
                raw_last_seen = node.last_heard
                raw_unmessagable = node.unmessagable

                if lat and lon:
                    location_str = get_city_state_offline(lat, lon)
                else:
                    location_str = "N/A"
                if raw_mqtt == 1:
                    mqtt = "True"
                else:
                    mqtt = "False"
                if raw_last_seen:
                    dt = datetime.fromtimestamp(float(raw_last_seen))
                    last_seen_str = dt.strftime("%Y-%m-%d %H:%M")
                else:
                    last_seen_str = "Never"
                if raw_unmessagable == 1:
                    unmessagable = "True"
                else:
                    unmessagable = "False"

                table.add_row(node_id, long_name, short_name, hw_model, role, location_str, altitude,
                              unmessagable, hops, channel, snr, channel_util, battery, uptime, mqtt, last_seen_str)

            # Render the table to the console window
            self.console_output.write(table)

    def _direct_nodes(self, command_arguments):
        # Access the DB Service via the Plugin Manager's registry
        db = self.plugin_mgr.services.get('db')
        if not db:
            self.console_output.write(
                "[bold red]Error: Database Service not loaded.[/]")
            return

        results: list[NodeInfo] = db.get_direct_nodes(limit=20)

        if not results:
            self.console_output.write(
                "[yellow]No results.[/]")
        else:
            # Create a pretty table
            table = Table(title=f"Search Results ({len(results)})")
            table.add_column("Node ID", style="cyan")
            table.add_column("Long Name", style="green")
            table.add_column("Short", style="magenta")
            table.add_column("Hardware", style="white")
            table.add_column("Role", style="blue")
            table.add_column("Location", style="red")
            table.add_column("Altitude", style="pink1")
            table.add_column("Unmessagable", style="violet")
            table.add_column("Hops", style="orange1")
            table.add_column("Channel", style="sky_blue2")
            table.add_column("SNR", style="yellow")
            table.add_column("Ch Util", style="purple3")
            table.add_column("Battery", style="light_green")
            table.add_column("Uptime", style="orchid")
            table.add_column("MQTT", style="purple")
            table.add_column("Seen", style="grey53")

            for node in results:
                # Handle potential None values safely
                node_id = str(node.node_id or "???")
                long_name = str(node.long_name or "Unknown")
                short_name = str(node.short_name or "Unknown")
                hw_model = str(node.hardware or "Unknown")
                role = str(node.role or "Unknown")
                lat = node.latitude
                lon = node.longitude
                altitude = str(
                    node.altitude) if node.altitude is not None else "N/A"
                snr = str(node.snr) if node.snr is not None else "N/A"
                raw_mqtt = node.via_mqtt
                channel = str(
                    node.channel) if node.channel is not None else "N/A"
                channel_util = str(
                    node.channel_utilization) if node.channel_utilization is not None else "Unknown"
                hops = str(
                    node.hops_away) if node.hops_away is not None else "N/A"
                battery = str(
                    node.battery_level) if node.battery_level is not None else "N/A"
                uptime = duration_to_str(
                    node.uptime) if node.uptime is not None else "Unknown"
                raw_last_seen = node.last_heard
                raw_unmessagable = node.unmessagable

                if lat and lon:
                    location_str = get_city_state_offline(lat, lon)
                else:
                    location_str = "N/A"
                if raw_mqtt == 1:
                    mqtt = "True"
                else:
                    mqtt = "False"
                if raw_last_seen:
                    dt = datetime.fromtimestamp(float(raw_last_seen))
                    last_seen_str = dt.strftime("%Y-%m-%d %H:%M")
                else:
                    last_seen_str = "Never"
                if raw_unmessagable == 1:
                    unmessagable = "True"
                else:
                    unmessagable = "False"

                table.add_row(node_id, long_name, short_name, hw_model, role, location_str, altitude,
                              unmessagable, hops, channel, snr, channel_util, battery, uptime, mqtt, last_seen_str)

            # Render the table to the console window
            self.console_output.write(table)

    def _neighbor_nodes(self, command_arguments):
        # Access the DB Service via the Plugin Manager's registry
        db = self.plugin_mgr.services.get('db')
        if not db:
            self.console_output.write(
                "[bold red]Error: Database Service not loaded.[/]")
            return

        results: list[NodeInfo] = db.get_neighbor_nodes(limit=20)

        if not results:
            self.console_output.write(
                "[yellow]No results.[/]")
        else:
            # Create a pretty table
            table = Table(title=f"Search Results ({len(results)})")
            table.add_column("Node ID", style="cyan")
            table.add_column("Long Name", style="green")
            table.add_column("Short", style="magenta")
            table.add_column("Hardware", style="white")
            table.add_column("Role", style="blue")
            table.add_column("Location", style="red")
            table.add_column("Altitude", style="pink1")
            table.add_column("Unmessagable", style="violet")
            table.add_column("Hops", style="orange1")
            table.add_column("Channel", style="sky_blue2")
            table.add_column("SNR", style="yellow")
            table.add_column("Ch Util", style="purple3")
            table.add_column("Battery", style="light_green")
            table.add_column("Uptime", style="orchid")
            table.add_column("MQTT", style="purple")
            table.add_column("Seen", style="grey53")

            for node in results:
                # Handle potential None values safely
                node_id = str(node.node_id or "???")
                long_name = str(node.long_name or "Unknown")
                short_name = str(node.short_name or "Unknown")
                hw_model = str(node.hardware or "Unknown")
                role = str(node.role or "Unknown")
                lat = node.latitude
                lon = node.longitude
                altitude = str(
                    node.altitude) if node.altitude is not None else "N/A"
                snr = str(node.snr) if node.snr is not None else "N/A"
                raw_mqtt = node.via_mqtt
                channel = str(
                    node.channel) if node.channel is not None else "N/A"
                channel_util = str(
                    node.channel_utilization) if node.channel_utilization is not None else "Unknown"
                hops = str(
                    node.hops_away) if node.hops_away is not None else "N/A"
                battery = str(
                    node.battery_level) if node.battery_level is not None else "N/A"
                uptime = duration_to_str(
                    node.uptime) if node.uptime is not None else "Unknown"
                raw_last_seen = node.last_heard
                raw_unmessagable = node.unmessagable

                if lat and lon:
                    location_str = get_city_state_offline(lat, lon)
                else:
                    location_str = "N/A"
                if raw_mqtt == 1:
                    mqtt = "True"
                else:
                    mqtt = "False"
                if raw_last_seen:
                    dt = datetime.fromtimestamp(float(raw_last_seen))
                    last_seen_str = dt.strftime("%Y-%m-%d %H:%M")
                else:
                    last_seen_str = "Never"
                if raw_unmessagable == 1:
                    unmessagable = "True"
                else:
                    unmessagable = "False"

                table.add_row(node_id, long_name, short_name, hw_model, role, location_str, altitude,
                              unmessagable, hops, channel, snr, channel_util, battery, uptime, mqtt, last_seen_str)

            # Render the table to the console window
            self.console_output.write(table)

    def _stats_command(self, command_arguments):
        if not command_arguments:
            self.console_output.write(
                "[red]Usage: stats <channels|commands|users>[/]")
            return
        db = self.plugin_mgr.services.get('db')
        if not db:
            self.console_output.write(
                "[bold red]Error: Database Service not loaded.[/]")
            return
        mesh = self.plugin_mgr.services.get('mesh')
        if not mesh:
            self.console_output.write(
                "[bold red]Error: Meshtastic Service not loaded.[/]")
            return
        clean_args = command_arguments[0].lower()
        if clean_args == "channels":
            channel_stats: list[ChannelStat] = db.get_channel_usage()
            table = Table(title="Channel Usage")
            table.add_column("Channel", style="cyan")
            table.add_column("Messages", style="green")
            for stat in channel_stats:
                raw_channel = stat.channel
                channel_name = self._get_channel_name(raw_channel)
                count = str(
                    stat.count) if stat.count is not None else "Unknown"
                table.add_row(channel_name, count)
            self.console_output.write(table)
        elif clean_args == "commands":
            command_stats: list[CommandStat] = db.get_top_commands(limit=10)
            table = Table(title="Bot Command Usage")
            table.add_column("Command", style="cyan")
            table.add_column("Invocations", style="green")
            for stat in command_stats:
                table.add_row(stat.command, str(stat.count))
            self.console_output.write(table)
        elif clean_args == "users":
            talker_stats: list[UserStat] = db.get_top_talkers(limit=20)
            table = Table(title="Top Talkers")
            table.add_column("User", style="cyan")
            table.add_column("Channel", style="green")
            table.add_column("Count", style="red")
            for stat in talker_stats:
                if stat.node_id is not None:
                    user_id = str(stat.node_id)
                    user_info = db.get_node(user_id)
                    if user_info is not None and user_info.long_name:
                        user_id = f"{user_info.long_name} ({user_id})"
                else:
                    user_id = "Unknown"
                raw_channel = stat.channel
                channel_name = self._get_channel_name(raw_channel)
                count = str(
                    stat.count) if stat.count is not None else "Unknown"
                table.add_row(user_id, channel_name, count)
            self.console_output.write(table)
        else:
            self.console_output.write(
                "[red]Usage: stats <channels|commands|users>[/]")

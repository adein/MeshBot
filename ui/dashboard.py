import logging
from datetime import datetime

import yaml
from rich.table import Table
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Input, RichLog
from textual import events, on

from core.event_bus import EventBus
from core.plugin_manager import PluginManager
from core.scheduler import BotScheduler
from ui.log_handler import TextualLogHandler
from utils.geo_utils import get_city_state_offline


class BotDashboard(App):
    """Textual-based TUI Dashboard for MeshBot."""

    CSS = """
    Screen {
        layout: grid;
        grid-size: 1 3;
        /* Top: 60% of vertical space
           Middle: Remaining space (approx 30-40%)
           Bottom: EXACTLY 4 rows (3 for Input + 1 for margin)
        */
        grid-rows: 60% 1fr 4;
    }

    #system_log {
        border: solid green;
        background: $surface;
        height: 100%;
    }

    #console_output {
        border: solid yellow;
        background: $surface;
        height: 100%;
    }

    Input {
        /* Force height to 3 so it never shrinks */
        height: 3; 
        width: 100%;
        border: solid red;
        
        margin-bottom: 1;
    }
    """

    def __init__(self, plugin_mgr: PluginManager, scheduler: BotScheduler, event_bus: EventBus):
        super().__init__()
        self.plugin_mgr: PluginManager = plugin_mgr
        self.scheduler: BotScheduler = scheduler
        self.event_bus: EventBus = event_bus
        self.console_output: RichLog = RichLog(
            highlight=True, markup=True, id="console_output")
        self.system_log: RichLog = RichLog(
            highlight=True, markup=True, id="system_log")
        self.command_history: list[str] = []
        self.history_index: int = 0

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

        self.system_log.border_title = "System Activity"
        yield self.system_log

        self.console_output.border_title = "Command Output"
        yield self.console_output

        yield Input(placeholder="Type a command...", id="command_input")
        yield Footer()

    def on_mount(self):
        """Called when the app starts. Setup logging hook."""
        # Add our custom handler to the root logger
        handler = TextualLogHandler(self.system_log)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(message)s')
        handler.setFormatter(formatter)
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)
        self.console_output.write(
            "[bold green]Welcome to the MeshBot admin console. Type help or ? to list commands.[/]")
        self.console_output.write("[bold yellow]Admin Console Ready.[/]")
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
                "  [cyan]node_search[/]: Search the node database.")
            self.console_output.write(
                "  [cyan]reload[/]: Reload configuration and modules.")
            self.console_output.write(
                "  [cyan]stats[/]: Show bot and mesh stats.")
            self.console_output.write(
                "  [cyan]status[/]: Show status of all modules.")
            self.console_output.write(
                "  [cyan]toggle <module_name>[/]: Enable/Disable a module.")

        elif base == "node_search":
            if not args:
                self.console_output.write(
                    "[red]Usage: node_search <name or id>[/]")
                return

            # Access the DB Service via the Plugin Manager's registry
            db = self.plugin_mgr.services.get('db')
            if not db:
                self.console_output.write(
                    "[bold red]Error: Database Service not loaded.[/]")
                return

            clean_args = ' '.join(args)
            self.console_output.write(
                f"Searching for: [bold cyan]'{clean_args}'[/]...")
            results = db.search_nodes(clean_args, limit=20)

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
                table.add_column("SNR", style="yellow")
                table.add_column("MQTT", style="purple")
                table.add_column("Channel", style="sky_blue2")
                table.add_column("Hops", style="orange1")
                table.add_column("Unmessagable", style="violet")
                table.add_column("Time", style="grey53")

                for row in results:
                    # Handle potential None values safely
                    node_id = str(row[0] or "???")
                    long_name = str(row[1] or "Unknown")
                    short_name = str(row[2] or "Unknown")
                    hw_model = str(row[3] or "Unknown")
                    role = str(row[4] or "Unknown")
                    lat = row[5]
                    lon = row[6]
                    altitude = str(row[7]) if row[7] is not None else "N/A"
                    snr = str(row[8]) if row[8] is not None else "N/A"
                    raw_mqtt = row[9]
                    channel = str(row[10]) if row[10] is not None else "N/A"
                    hops = str(row[11]) if row[11] is not None else "N/A"
                    raw_last_seen = row[12]
                    raw_unmessagable = row[13]

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

                    table.add_row(node_id, long_name, short_name, hw_model, role, location_str,
                                  altitude, snr, mqtt, channel, hops, unmessagable, last_seen_str)

                # Render the table to the console window
                self.console_output.write(table)

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
            if not args:
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
            clean_args = args[0].lower()
            if clean_args == "channels":
                rows = db.get_channel_usage()
                table = Table(title="Channel Usage")
                table.add_column("Channel", style="cyan")
                table.add_column("Messages", style="green")
                for row in rows:
                    channel = str(row[0]) if row[0] is not None else "Unknown"
                    count = str(row[1]) if row[1] is not None else "Unknown"
                    table.add_row(channel, count)
                self.console_output.write(table)
            elif clean_args == "commands":
                rows = db.get_top_commands(limit=10)
                table = Table(title="Bot Command Usage")
                table.add_column("Command", style="cyan")
                table.add_column("Invocations", style="green")
                for row in rows:
                    command = str(row[0]) if row[0] is not None else "Unknown"
                    count = str(row[1]) if row[1] is not None else "Unknown"
                    table.add_row(command, count)
                self.console_output.write(table)
            elif clean_args == "users":
                rows = db.get_top_talkers(limit=20)
                table = Table(title="Top Talkers")
                table.add_column("User", style="cyan")
                table.add_column("Channel", style="green")
                table.add_column("Count", style="red")
                for row in rows:
                    if row[0] is not None:
                        user_id = str(row[0])
                        user_info = db.get_node(user_id)
                        if user_info is not None and user_info.long_name:
                            user_id = f"{user_info.long_name} ({user_id})"
                    else:
                        user_id = "Unknown"
                    if row[1] == -1:
                        channel = "DM"
                    elif row[1] is not None:
                        channel = str(row[1])
                    else:
                        channel = "Unknown"
                    count = str(row[2]) if row[1] is not None else "Unknown"
                    table.add_row(user_id, channel, count)
                self.console_output.write(table)
            else:
                self.console_output.write(
                    "[red]Usage: stats <channels|commands|users>[/]")

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

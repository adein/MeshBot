from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, Input, RichLog, Static
from textual.containers import Container
from textual import on
import logging
import yaml

from core.plugin_manager import PluginManager
from core.scheduler import BotScheduler
from ui.log_handler import TextualLogHandler

class BotDashboard(App):
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

    def __init__(self, plugin_mgr, scheduler, event_bus):
        super().__init__()
        self.plugin_mgr = plugin_mgr
        self.scheduler = scheduler
        self.event_bus = event_bus

    def _load_config(self):
        try:
            with open("config.yaml", "r") as f:
                return yaml.safe_load(f)
        except FileNotFoundError:
            logging.error("config.yaml not found!")
            self.console_output.write(f"[bold red]config.yaml not found!")
            self.exit()

    def compose(self) -> ComposeResult:
        """Create the UI layout."""
        yield Header(show_clock=True)
        
        self.system_log = RichLog(highlight=True, markup=True, id="system_log")
        self.system_log.border_title = "System Activity"
        yield self.system_log
        
        self.console_output = RichLog(highlight=True, markup=True, id="console_output")
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
        self.console_output.write("[bold green]Welcome to the MeshBot admin console. Type help or ? to list commands.[/]")
        self.console_output.write("[bold yellow]Admin Console Ready.[/]")

    @on(Input.Submitted, "#command_input")
    def handle_input(self, event: Input.Submitted):
        """Runs when user presses Enter."""
        command = event.value.strip()
        self.query_one("#command_input").value = "" # Clear input

        if not command:
            return

        self.console_output.write(f"[bold]> {command}[/]")
        self.process_command(command)

    def process_command(self, cmd_text):
        """
        Console commands.
        """
        parts = cmd_text.split()
        base = parts[0].lower()
        args = parts[1] if len(parts) > 1 else None

        if base == "exit":
            self.exit()
        
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

        elif base == "status":
            self.console_output.write("--- STATUS REPORT ---")
            for name, mod in self.plugin_mgr.get_all_modules().items():
                status = "[green]ENABLED[/]" if mod.is_enabled() else "[red]DISABLED[/]"
                self.console_output.write(f"{status} {name}")
            self.console_output.write("---------------------")
        
        elif base == "toggle" and args:
            mod = self.plugin_mgr.get_module(args)
            if mod:
                mod.config['enabled'] = not mod.config['enabled']
                state = "Enabled" if mod.config['enabled'] else "Disabled"
                self.console_output.write(f"Module {args} is now {state}")
                self.scheduler.reload_jobs()
            else:
                self.console_output.write(f"[bold red]Module {args} not found.[/]")

        elif base == "help" or base == "?":
            self.console_output.write("[bold]Available Commands:[/]")
            self.console_output.write("  [cyan]help or ?[/]: Show this help message.")
            self.console_output.write("  [cyan]exit[/]: Exit the bot.")
            self.console_output.write("  [cyan]reload[/]: Reload configuration and modules.")
            self.console_output.write("  [cyan]status[/]: Show status of all modules.")
            self.console_output.write("  [cyan]toggle <module_name>[/]: Enable/Disable a module.")
            
        else:
            self.console_output.write(f"[yellow]Unknown command: {base}[/]")

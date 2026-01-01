from core.command_dispatcher import CommandData
from interfaces.bot_module import BotModule


GENERAL_HELP = "General commands: !about, !michmesh, !nodesearch {query}, !ping, !stats {type}"
WEATHER_HELP = "Weather commands: !alerts {location}, !forecast {location}, !weather {location}"
HELP_ERROR = 'Unknown command. Try "!help" or "!help command"'

ABOUT_CMD_HELP = 'Get information about this bot or how to get in contact with the owner'
MICHMESH_CMD_HELP = 'Get information about configuring your meshtastic node to talk with \
    Michiganders'
NODESEARCH_CMD_HELP = 'Search for information about a node by long name, short name, \
    or node ID. Example: !nodesearch testnode'
PING_CMD_HELP = 'Test your connection and reception by requesting a response back. Example: !ping'
STATS_CMD_HELP = 'View stats about most frequenct bot commands, channel activity, \
    or most active users. Example !stats users'

ALERTS_CMD_HELP = 'Get NWS alerts for your area using zip or city,state. \
    Example: !alerts detroit, mi'
FORECAST_CMD_HELP = 'Get NWS forecast for your area using zip or city,state. \
    Example: !forecast detroit, mi'
WEATHER_CMD_HELP = 'Get NWS current conditions from nearest weather station using \
    zip or city,state. Example: !weather 12345'


class Help(BotModule):
    """
    Module to respond to 'help' commands with usage information.
    """

    def __init__(self, name: str, config, global_services: dict, my_node: str):
        super().__init__(name, config, global_services, my_node)
        self.all_help: str = GENERAL_HELP + "\n" + WEATHER_HELP
        # Subscribe to the command event
        if self.event_bus:
            self.event_bus.subscribe("bot.command.help", self._handle_command)

    def execute(self):
        # Triggered, so this is empty
        pass

    def _handle_command(self, data: CommandData):
        if not self.is_enabled():
            return
        if data.sender_id is None or (data.receiver_id is None and data.channel is None):
            self.logger.warning(
                "Help command is missing essential message data")
            return

        arguments = data.parameters
        if arguments is None or len(arguments) <= 0:
            self.mesh_service.send_reply(self.all_help, data)
        elif len(arguments) == 1:
            help_subcommand = arguments[0].removeprefix('!')
            if help_subcommand == "about":
                self.mesh_service.send_reply(ABOUT_CMD_HELP, data)
            elif help_subcommand == "michmesh":
                self.mesh_service.send_reply(MICHMESH_CMD_HELP, data)
            elif help_subcommand == "nodesearch":
                self.mesh_service.send_reply(NODESEARCH_CMD_HELP, data)
            elif help_subcommand == "ping":
                self.mesh_service.send_reply(PING_CMD_HELP, data)
            elif help_subcommand == "stats":
                self.mesh_service.send_reply(STATS_CMD_HELP, data)
            elif help_subcommand == "alerts":
                self.mesh_service.send_reply(ALERTS_CMD_HELP, data)
            elif help_subcommand == "forecast":
                self.mesh_service.send_reply(FORECAST_CMD_HELP, data)
            elif help_subcommand == "weather":
                self.mesh_service.send_reply(WEATHER_CMD_HELP, data)
            else:
                self.mesh_service.send_reply(HELP_ERROR, data)
        else:
            self.mesh_service.send_reply(HELP_ERROR, data)

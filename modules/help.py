from core.command_dispatcher import CommandData
from interfaces.bot_module import BotModule
from services.meshtastic_service import TO_SEND_TOPIC, TextToSend


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
        self.logger.info(
            "EVENT TRIGGERED: received help command with payload: %s", data)
        if data.sender_id is None or (data.receiver_id is None and data.channel is None):
            self.logger.info("Help command is missing essential message data")
            return

        arguments = data.parameters
        if arguments is None or len(arguments) <= 0:
            self._send_message(self.all_help, data)
        elif len(arguments) == 1:
            help_subcommand = arguments[0].removeprefix('!')
            if help_subcommand == "about":
                self._send_message(ABOUT_CMD_HELP, data)
            elif help_subcommand == "michmesh":
                self._send_message(MICHMESH_CMD_HELP, data)
            elif help_subcommand == "nodesearch":
                self._send_message(NODESEARCH_CMD_HELP, data)
            elif help_subcommand == "ping":
                self._send_message(PING_CMD_HELP, data)
            elif help_subcommand == "stats":
                self._send_message(STATS_CMD_HELP, data)
            elif help_subcommand == "alerts":
                self._send_message(ALERTS_CMD_HELP, data)
            elif help_subcommand == "forecast":
                self._send_message(FORECAST_CMD_HELP, data)
            elif help_subcommand == "weather":
                self._send_message(WEATHER_CMD_HELP, data)
            else:
                self._send_message(HELP_ERROR, data)
        else:
            self._send_message(HELP_ERROR, data)

    def _send_message(self, message, command_data):
        from_id = command_data.sender_id
        to_id = command_data.receiver_id
        channel_num = command_data.channel
        if from_id is not None and to_id == self.my_node_id:
            message_data = TextToSend(
                message,
                from_id,
                None,
                False
            )
            self.logger.info(
                "Help command responding with payload: %s", message_data)
            self.event_bus.publish(TO_SEND_TOPIC, message_data)
        elif channel_num is not None and to_id == "^all":
            message_data = TextToSend(
                message,
                None,
                channel_num,
                False
            )
            self.logger.info(
                "Help command responding with payload: %s", message_data)
            self.event_bus.publish(TO_SEND_TOPIC, message_data)
        else:
            self.logger.warning("Unable to handle help command!")

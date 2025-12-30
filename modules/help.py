from interfaces.bot_module import BotModule
from services.meshtastic_service import TextToSend

class Help(BotModule):
    GENERAL_HELP = "General commands: !about, !michmesh, !nodesearch, !ping, !stats"
    WEATHER_HELP = "Weather commands: !alerts {location}, !forecast {location}, !weather {location}"
    HELP_ERROR = 'Unknown command. Try "!help" or "!help command"'

    ABOUT_CMD_HELP = 'Get information about this bot or how to get in contact with the owner'
    MICHMESH_CMD_HELP = 'Get information about configuring your meshtastic node to talk with Michiganders'
    NODESEARCH_CMD_HELP = 'Search for information about a node by long name, short name, or node ID. Example: !nodesearch testnode'
    PING_CMD_HELP = 'Test your connection and reception by requesting a response back. Example: !ping'
    STATS_CMD_HELP = 'View stats about bot usage, channel activity, or user activity. Example !stats channels'

    ALERTS_CMD_HELP = 'Get NWS alerts for your area using zip or city,state. Example: !alerts detroit, mi'
    FORECAST_CMD_HELP = 'Get NWS forecast for your area using zip or city,state. Example: !forecast detroit, mi'
    WEATHER_CMD_HELP = 'Get NWS current conditions from nearest weather station using zip or city,state. Example: !weather 12345'

    def __init__(self, name, config, global_services, my_node=None):
        super().__init__(name, config, global_services, my_node)
        self.ALL_HELP = self.GENERAL_HELP + "\n" + self.WEATHER_HELP
        # Listen for the command event
        if self.event_bus:
            self.event_bus.subscribe("bot.command.help", self._handle_command)

    def execute(self):
        # Triggered vs scheduled, so this is empty
        pass

    def _handle_command(self, data):
        if not self.is_enabled():
            return
        self.logger.info(f"EVENT TRIGGERED: received help command with payload: {data}")
        if data.sender_id is None or (data.receiver_id is None and data.channel is None):
            self.logger.info(f"Help command is missing essential message data")
            return

        arguments = data.parameters
        if arguments == None or len(arguments) <= 0:
            self._send_message(self.ALL_HELP, data)
            return
        elif len(arguments) == 1:
            help_subcommand = arguments[0].removeprefix('!')
            if help_subcommand == "about":
                self._send_message(self.ABOUT_CMD_HELP, data)
                return
            elif help_subcommand == "michmesh":
                self._send_message(self.MICHMESH_CMD_HELP, data)
                return
            elif help_subcommand == "nodesearch":
                self._send_message(self.NODESEARCH_CMD_HELP, data)
                return
            elif help_subcommand == "ping":
                self._send_message(self.PING_CMD_HELP, data)
                return
            elif help_subcommand == "stats":
                self._send_message(self.STATS_CMD_HELP, data)
                return
            elif help_subcommand == "alerts":
                self._send_message(self.ALERTS_CMD_HELP, data)
                return
            elif help_subcommand == "forecast":
                self._send_message(self.FORECAST_CMD_HELP, data)
                return
            elif help_subcommand == "weather":
                self._send_message(self.WEATHER_CMD_HELP, data)
                return
            else:
                self._send_message(self.HELP_ERROR, data)
                return
        else:
            self._send_message(self.HELP_ERROR, data)
            return

    def _send_message(self, message, command_data):
        from_id = command_data.sender_id
        to_id = command_data.receiver_id
        channel_num = command_data.channel
        if from_id != None and to_id == self.my_node_id:
            message_data = TextToSend(
                    message,
                    from_id,
                    None,
                    False
            )
            self.logger.info(f"Help command responding with payload: {message_data}")
            self.event_bus.publish("meshtastic_service.to_send", message_data)
        elif channel_num != None and to_id == "^all":
            message_data = TextToSend(
                    message,
                    None,
                    channel_num,
                    False
            )
            self.logger.info(f"Help command responding with payload: {message_data}")
            self.event_bus.publish("meshtastic_service.to_send", message_data)
        else:
            self.logger.warn(f"Unable to handle help command!")
 

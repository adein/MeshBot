from core.command_dispatcher import CommandData
from interfaces.bot_module import BotModule
from services.meshtastic_service import TO_SEND_TOPIC, TextToSend


class StatsReporter(BotModule):
    """
    Module to respond to 'stats' commands with usage statistics.
    """

    def __init__(self, name: str, config, global_services: dict, my_node: str):
        super().__init__(name, config, global_services, my_node)
        if self.event_bus:
            self.event_bus.subscribe(
                "bot.command.stats", self.handle_stats_request)

    def execute(self):
        # Triggered, so this is empty
        pass

    def handle_stats_request(self, data: CommandData):
        if not self.is_enabled():
            return
        if not self.db:
            return
        self.logger.info(
            "EVENT TRIGGERED: received stats request event with data %s", data)
        if data.sender_id is None or (data.receiver_id is None and data.channel is None):
            self.logger.warning(
                "Stats command is missing essential message data")
            return

        from_id = data.sender_id
        to_id = data.receiver_id
        channel_num = data.channel
        args = data.parameters
        mode = args[0] if args else "commands"

        output = []

        if mode == "commands":
            rows = self.db.get_top_commands()
            output.append("📊 Top Commands:")
            for cmd, count in rows:
                output.append(f"!{cmd}: {count}")

        elif mode == "users":
            rows = self.db.get_top_talkers()
            output.append("🗣️ Top Talkers (Channel | Count | User)")
            for user, channel, count in rows:
                user_display = user
                user_info = self.db.get_node(user)
                if user_info is not None and user_info.long_name:
                    user_display = user_info.long_name
                chan_str = f"Ch {channel}"
                if channel == -1:
                    chan_str = "DM  "
                output.append(f"{chan_str} | {count} | {user_display}")

        elif mode == "channels":
            rows = self.db.get_channel_usage()
            output.append("📻 Channel Usage:")
            for channel, count in rows:
                output.append(f"Ch {channel}: {count} msgs")

        else:
            output.append("Usage: !stats [commands|users|channels]")
        # Reply via the service
        message = "\n".join(output)
        if from_id is not None and to_id == self.my_node_id:
            message_data = TextToSend(
                message,
                from_id,
                None,
                False
            )
            self.logger.info(
                "Stats command responding with payload: %s", message_data)
            self.event_bus.publish(TO_SEND_TOPIC, message_data)
        elif channel_num is not None and to_id == "^all":
            message_data = TextToSend(
                message,
                None,
                channel_num,
                False
            )
            self.logger.info(
                "Stats command responding with payload: %s", message_data)
            self.event_bus.publish(TO_SEND_TOPIC, message_data)
        else:
            self.logger.warning("Unable to handle stats command!")

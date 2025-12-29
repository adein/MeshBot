from interfaces.bot_module import BotModule
from services.meshtastic_service import TextToSend

class StatsReporter(BotModule):
    def __init__(self, name, config, global_services, my_node=None):
        super().__init__(name, config, global_services, my_node)
        if self.event_bus:
            self.event_bus.subscribe("bot.command.stats", self.handle_stats_request)

    def execute(self):
        pass

    def handle_stats_request(self, data):
        if not self.db:
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
                user_info = self.mesh_service.get_node_info(user)
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
        if from_id != None and to_id == self.my_node_id:
            message_data = TextToSend(
                    message,
                    from_id,
                    None,
                    False
            )
            self.logger.info(f"Stats command responding with payload: {message_data}")
            self.event_bus.publish("meshtastic_service.to_send", message_data)
        elif channel_num != None and to_id == "^all":
            message_data = TextToSend(
                    message,
                    None,
                    channel_num,
                    False
            )
            self.logger.info(f"Stats command responding with payload: {message_data}")
            self.event_bus.publish("meshtastic_service.to_send", message_data)
        else:
            self.logger.warn(f"Unable to handle stats command!")

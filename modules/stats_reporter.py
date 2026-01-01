from core.command_dispatcher import CommandData
from interfaces.bot_module import BotModule


class StatsReporter(BotModule):
    """
    Module to respond to 'stats' commands with usage statistics.
    """

    def __init__(self, name: str, config, global_services: dict, my_node: str):
        super().__init__(name, config, global_services, my_node)
        self.channel_0_name: str = self.config.get('channel_0_name', '0')
        self.channel_1_name: str = self.config.get('channel_1_name', '1')
        self.channel_2_name: str = self.config.get('channel_2_name', '2')
        self.channel_3_name: str = self.config.get('channel_3_name', '3')
        self.channel_4_name: str = self.config.get('channel_4_name', '4')
        self.channel_5_name: str = self.config.get('channel_5_name', '5')
        self.channel_6_name: str = self.config.get('channel_6_name', '6')
        self.channel_7_name: str = self.config.get('channel_7_name', '7')
        if self.event_bus:
            self.event_bus.subscribe(
                "bot.command.stats", self.handle_stats_request)

    def execute(self):
        # Triggered, so this is empty
        pass

    def _get_channel_name(self, channel_id: int) -> str:
        channel_names = {
            0: self.channel_0_name,
            1: self.channel_1_name,
            2: self.channel_2_name,
            3: self.channel_3_name,
            4: self.channel_4_name,
            5: self.channel_5_name,
            6: self.channel_6_name,
            7: self.channel_7_name,
        }
        return channel_names.get(channel_id, str(channel_id))

    def handle_stats_request(self, data: CommandData):
        if not self.is_enabled():
            self.logger.warning(
                "Stats command triggered, but module is disabled.")
            return
        if not self.db:
            self.logger.error(
                "Stats command could not access the database!")
            return
        if data.sender_id is None or (data.receiver_id is None and data.channel is None):
            self.logger.debug(
                "Stats command is missing essential message data")
            return

        args = data.parameters
        mode = args[0] if args else "commands"
        output = []
        self.logger.info("Handling stats command with mode: %s", mode)
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
                channel_name = self._get_channel_name(channel)
                if channel_name is None:
                    channel_name = f"{channel}"
                if channel == -1:
                    channel_name = "DM w/ Bot"
                output.append(f"{channel_name} | {count} | {user_display}")

        elif mode == "channels":
            rows = self.db.get_channel_usage()
            output.append("📻 Channel Usage:")
            for channel, count in rows:
                channel_name = self._get_channel_name(channel)
                if channel_name is None:
                    channel_name = f"{channel}"
                output.append(f"{channel_name}: {count} msgs")

        else:
            output.append("Usage: !stats [commands|users|channels]")
        # Reply via the service
        message = "\n".join(output)
        self.mesh_service.send_reply(message, data)

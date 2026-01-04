from interfaces.bot_module import BotModule
from models.command import CommandData
from models.statistics import CommandStat, UserStat, ChannelStat


class StatsReporter(BotModule):
    """
    Module to respond to 'stats' commands with usage statistics.
    """

    def __init__(self, name: str, config, root_config, global_services: dict, my_node: str):
        super().__init__(name, config, root_config, global_services, my_node)
        core_config = root_config.get('core', {})
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
        if self.event_bus:
            self.event_bus.subscribe(
                "bot.command.stats", self.handle_stats_request)

    def execute(self):
        # Triggered, so this is empty
        pass

    def _get_channel_name(self, channel_id: int) -> str:
        if channel_id == -1:
            return "DM w/ Bot"
        return self.channel_names.get(channel_id, str(channel_id))

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
            command_stats: list[CommandStat] = self.db.get_top_commands()
            output.append("📊 Top Commands:")
            for stat in command_stats:
                output.append(f"!{stat.command}: {stat.count}")

        elif mode == "users":
            talker_stats: list[UserStat] = self.db.get_top_talkers()
            output.append("🗣️ Top Talkers (Channel | Count | User)")
            for stat in talker_stats:
                user = stat.node_id
                channel = stat.channel
                count = stat.count
                user_display = user
                user_info = self.db.get_node(user)
                if user_info is not None and user_info.long_name:
                    user_display = user_info.long_name
                channel_name = self._get_channel_name(channel)
                output.append(f"{channel_name} | {count} | {user_display}")

        elif mode == "channels":
            channel_stats: list[ChannelStat] = self.db.get_channel_usage()
            output.append("📻 Channel Usage:")
            for stat in channel_stats:
                channel_name = self._get_channel_name(stat.channel)
                output.append(f"{channel_name}: {stat.count} msgs")

        else:
            output.append("Usage: !stats [commands|users|channels]")
        # Reply via the service
        message = "\n".join(output)
        self.mesh_service.send_reply(message, data)

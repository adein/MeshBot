from core.command_dispatcher import CommandData
from interfaces.bot_module import BotModule


INFO = "MichMesh setup information: https://tinyurl.com/michmesh"


class MichMesh(BotModule):
    """
    Module to respond to 'michmesh' commands with mesh setup information.
    """

    def __init__(self, name: str, config, root_config, global_services: dict, my_node: str):
        super().__init__(name, config, root_config, global_services, my_node)
        # Listen for the command event
        if self.event_bus:
            self.event_bus.subscribe(
                "bot.command.michmesh", self._handle_command)

    def execute(self):
        # Triggered, so this is empty
        pass

    def _handle_command(self, data: CommandData):
        if not self.is_enabled():
            self.logger.warning(
                "MichMesh command triggered, but module is disabled.")
            return
        if data.sender_id is None or (data.receiver_id is None and data.channel is None):
            self.logger.debug(
                "MichMesh command is missing essential message data")
            return
        self.logger.info("Handling michmesh command...")
        self.mesh_service.send_reply(INFO, data)

from core.command_dispatcher import CommandData
from interfaces.bot_module import BotModule


INFO = "MichMesh setup information: https://tinyurl.com/michmesh"


class MichMesh(BotModule):
    """
    Module to respond to 'michmesh' commands with mesh setup information.
    """

    def __init__(self, name: str, config, global_services: dict, my_node: str):
        super().__init__(name, config, global_services, my_node)
        # Listen for the command event
        if self.event_bus:
            self.event_bus.subscribe(
                "bot.command.michmesh", self._handle_command)

    def execute(self):
        # Triggered, so this is empty
        pass

    def _handle_command(self, data: CommandData):
        if not self.is_enabled():
            return
        if data.sender_id is None or (data.receiver_id is None and data.channel is None):
            self.logger.warning(
                "MichMesh command is missing essential message data")
            return
        self.mesh_service.send_reply(INFO, data)

from core.command_dispatcher import CommandData
from interfaces.bot_module import BotModule
from services.meshtastic_service import TO_SEND_TOPIC, TextToSend


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
        self.logger.info(
            "EVENT TRIGGERED: received michmesh command with payload: %s", data)
        if data.sender_id is None or (data.receiver_id is None and data.channel is None):
            self.logger.info(
                "MichMesh command is missing essential message data")
            return
        self._send_message(INFO, data)

    def _send_message(self, message: str, command_data: CommandData):
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
                "MichMesh command responding with payload: %s", message_data)
            self.event_bus.publish(TO_SEND_TOPIC, message_data)
        elif channel_num is not None and to_id == "^all":
            message_data = TextToSend(
                message,
                None,
                channel_num,
                False
            )
            self.logger.info(
                "MichMesh command responding with payload: %s", message_data)
            self.event_bus.publish(TO_SEND_TOPIC, message_data)
        else:
            self.logger.warning("Unable to handle michmesh command!")

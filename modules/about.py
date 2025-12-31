from core.command_dispatcher import CommandData
from interfaces.bot_module import BotModule
from services.meshtastic_service import TO_SEND_TOPIC, TextToSend


ABOUT = "MeshBot by Adein"
NOT_PROVIDED = "NOT_PROVIDED"


class About(BotModule):
    """
    Module to respond to 'about' commands with bot information.
    """

    def __init__(self, name: str, config, global_services: dict, my_node: str):
        super().__init__(name, config, global_services, my_node)
        # Subscribe to the command event
        if self.event_bus:
            self.event_bus.subscribe("bot.command.about", self._handle_command)
        self.contact_node_id: str = self.config.get(
            'contact_node_id', NOT_PROVIDED)
        self.contact_email: str = self.config.get(
            'contact_email', NOT_PROVIDED)

    def execute(self):
        # Module is triggered by command, so this is empty
        pass

    def _handle_command(self, data: CommandData):
        if not self.is_enabled():
            return
        self.logger.info(
            "EVENT TRIGGERED: received about command with payload: %s", data)
        if data.sender_id is None or (data.receiver_id is None and data.channel is None):
            self.logger.info(
                "About command is missing essential message data")
            return
        message_to_send = ABOUT
        contact_message = None
        if self.contact_node_id != NOT_PROVIDED:
            contact_message = f"For any issues, requests, etc - Contact me at {self.contact_node_id}"
        if self.contact_email != NOT_PROVIDED:
            if contact_message is None:
                contact_message = f"For any issues, requests, etc - Email me at {self.contact_email}"
            else:
                contact_message = contact_message + \
                    f" or by email at {self.contact_email}"
        if contact_message is not None:
            message_to_send = message_to_send + "\n" + contact_message
        self._send_message(message_to_send, data)

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
                "About command responding with payload: %s", message_data)
            self.event_bus.publish(TO_SEND_TOPIC, message_data)
        elif channel_num is not None and to_id == "^all":
            message_data = TextToSend(
                message,
                None,
                channel_num,
                False
            )
            self.logger.info(
                "About command responding with payload: %s", message_data)
            self.event_bus.publish(TO_SEND_TOPIC, message_data)
        else:
            self.logger.warning("Unable to handle about command!")

from interfaces.bot_module import BotModule
from models.command import CommandData


ABOUT = "MeshBot 🤖 by Adein"
NOT_PROVIDED = "NOT_PROVIDED"


class About(BotModule):
    """
    Module to respond to 'about' commands with bot information.
    """

    def __init__(self, name: str, config, root_config, global_services: dict, my_node: str):
        super().__init__(name, config, root_config, global_services, my_node)
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
            self.logger.warning(
                "About command triggered, but module is disabled.")
            return
        if data.sender_id is None or (data.receiver_id is None and data.channel is None):
            self.logger.debug(
                "About command is missing essential message data")
            return
        if self.is_dm_only() and not data.is_dm:
            self.logger.debug(
                "About command received in non-DM, but module is DM-only.")
            return
        self.logger.info("Handling about command...")
        message_to_send = ABOUT
        contact_message = None
        if self.contact_node_id != NOT_PROVIDED:
            contact_message = f"For any issues, requests, etc - 📟 Message me at {self.contact_node_id}"
        if self.contact_email != NOT_PROVIDED:
            if contact_message is None:
                contact_message = f"For any issues, requests, etc - 📧 Email me at {self.contact_email}"
            else:
                contact_message = contact_message + \
                    f" or by 📧 email at {self.contact_email}"
        if contact_message is not None:
            message_to_send = message_to_send + "\n" + contact_message
        self.mesh_service.send_reply(message_to_send, data)

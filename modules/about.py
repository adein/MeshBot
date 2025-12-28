from interfaces.bot_module import BotModule
from services.meshtastic_service import TextToSend

class About(BotModule):
    ABOUT = "MeshBot by Adein"

    def __init__(self, name, config, event_bus=None, my_node=None, mesh_svc=None):
        super().__init__(name, config, event_bus, my_node, mesh_svc)
        # Listen for the command event
        if self.event_bus:
            self.event_bus.subscribe("bot.command.about", self._handle_command)
        self.CONTACT_NODE_ID = self.config.get('contact_node_id', "NOT_PROVIDED")
        self.CONTACT_EMAIL = self.config.get('contact_email', "NOT_PROVIDED")
        
    def execute(self):
        # Triggered vs scheduled, so this is empty
        pass

    def _handle_command(self, data):
        if not self.is_enabled():
            return
        self.logger.info(f"EVENT TRIGGERED: received about command with payload: {data}")
        if data.sender_id is None or (data.receiver_id is None and data.channel is None):
            self.logger.info(f"About command is missing essential message data")
            return
        message_to_send = self.ABOUT
        contact_message = None
        if self.CONTACT_NODE_ID != "NOT_PROVIDED":
            contact_message = f"For any issues, requests, etc - Contact me at {self.CONTACT_NODE_ID}"
        if self.CONTACT_EMAIL != "NOT_PROVIDED":
            if contact_message == None:
                contact_message = f"For any issues, requests, etc - Email me at {self.CONTACT_EMAIL}"
            else:
                contact_message = contact_message + f" or by email at {self.CONTACT_EMAIL}"
        if contact_message != None:
            message_to_send = message_to_send + "\n" + contact_message
        self._send_message(message_to_send, data)

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
            self.logger.info(f"About command responding with payload: {message_data}")
            self.event_bus.publish("meshtastic_service.to_send", message_data)
        elif channel_num != None and to_id == "^all":
            message_data = TextToSend(
                    message,
                    None,
                    channel_num,
                    False
            )
            self.logger.info(f"About command responding with payload: {message_data}")
            self.event_bus.publish("meshtastic_service.to_send", message_data)
        else:
            self.logger.warn(f"Unable to handle about command!")
 

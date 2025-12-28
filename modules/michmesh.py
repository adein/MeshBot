from interfaces.bot_module import BotModule
from services.meshtastic_service import TextToSend

class MichMesh(BotModule):
    INFO = "MichMesh setup information: https://tinyurl.com/michmesh"

    def __init__(self, name, config, event_bus=None, my_node=None, mesh_svc=None):
        super().__init__(name, config, event_bus, my_node, mesh_svc)
        # Listen for the command event
        if self.event_bus:
            self.event_bus.subscribe("bot.command.michmesh", self._handle_command)

    def execute(self):
        # Triggered vs scheduled, so this is empty
        pass

    def _handle_command(self, data):
        if not self.is_enabled():
            return
        self.logger.info(f"EVENT TRIGGERED: received michmesh command with payload: {data}")
        if data.sender_id is None or (data.receiver_id is None and data.channel is None):
            self.logger.info(f"MichMesh command is missing essential message data")
            return
        self._send_message(self.INFO, data)

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
            self.logger.info(f"MichMesh command responding with payload: {message_data}")
            self.event_bus.publish("meshtastic_service.to_send", message_data)
        elif channel_num != None and to_id == "^all":
            message_data = TextToSend(
                    message,
                    None,
                    channel_num,
                    False
            )
            self.logger.info(f"MichMesh command responding with payload: {message_data}")
            self.event_bus.publish("meshtastic_service.to_send", message_data)
        else:
            self.logger.warn(f"Unable to handle michmesh command!")
 

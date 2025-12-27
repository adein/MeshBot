from interfaces.bot_module import BotModule
from services.meshtastic_service import TextToSend

class Ping(BotModule):
    def __init__(self, name, config, event_bus=None, my_node=None, mesh_svc=None):
        super().__init__(name, config, event_bus, my_node, mesh_svc)
        # Listen for the command event
        if self.event_bus:
            self.event_bus.subscribe("bot.command.ping", self._handle_command)

    def execute(self):
        # Triggered vs scheduled, so this is empty
        pass

    def _handle_command(self, data):
        if not self.is_enabled():
            return
        self.logger.info(f"EVENT TRIGGERED: received ping command with payload: {data}")
        if data.sender_id is None or (data.receiver_id is None and data.channel is None):
            self.logger.info(f"Ping command is missing essential message data")
            return
        from_id = data.sender_id
        to_id = data.receiver_id
        channel_num = data.channel
        via_mqtt = data.via_mqtt
        snr = data.rx_snr
        hops_away = data.hops_away
        message = ""
        sender = f"{from_id}"
        node_data = self.mesh_service.get_node_info(from_id)
        if node_data != None:
            if node_data.long_name != None:
                sender = f"{node_data.long_name}"
            elif node_data.short_name != None:
                sender = f"{node_data.short_name}"
        message = f"@'{sender}' Pong!"
        if via_mqtt == True:
            message = message + " Heard via MQTT."
        else:
            message = message + " Heard via LoRa radio."
            if snr != None or (node_data != None and node_data.snr != None) or hops_away != None or (node_data != None and node_data.hops_away != None):
                message = message + "\n"
                spacer = ""
                if snr != None:
                    message = message + spacer + f"SNR: {snr}"
                    spacer = ", "
                elif node_data != None and node_data.snr != None:
                    message = message + spacer + f"Previous SNR: {node_data.snr}"
                    spacer = ", "
                if hops_away != None:
                    message = message + spacer + f"Hops away: {hops_away}"
                    spacer = ", "
                elif node_data != None and node_data.hops_away != None:
                    message = message + spacer + f"Previous hops away: {node_data.hops_away}"
                    spacer = ", "
        if from_id != None and to_id == self.my_node_id:
            message_data = TextToSend(
                    message,
                    from_id,
                    None
            )
            self.logger.info(f"Ping command responding with payload: {message_data}")
            self.event_bus.publish("meshtastic_service.to_send", message_data)
        elif channel_num != None and to_id == "^all":
            message_data = TextToSend(
                    message,
                    None,
                    channel_num
            )
            self.logger.info(f"Ping command responding with payload: {message_data}")
            self.event_bus.publish("meshtastic_service.to_send", message_data)
        else:
            self.logger.warn(f"Unable to handle ping command!")


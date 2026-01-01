from core.command_dispatcher import CommandData
from interfaces.bot_module import BotModule


class Ping(BotModule):
    """
    Module to respond to 'ping' commands with 'pong' messages.
    """

    def __init__(self, name: str, config, global_services: dict, my_node: str):
        super().__init__(name, config, global_services, my_node)
        # Listen for the command event
        if self.event_bus:
            self.event_bus.subscribe("bot.command.ping", self._handle_command)

    def execute(self):
        # Triggered, so this is empty
        pass

    def _handle_command(self, data: CommandData):
        if not self.is_enabled():
            self.logger.warning(
                "Ping command triggered, but module is disabled.")
            return
        if data.sender_id is None or (data.receiver_id is None and data.channel is None):
            self.logger.debug(
                "Ping command is missing essential message data")
            return
        self.logger.info("Handling ping command...")
        from_id = data.sender_id
        via_mqtt = data.via_mqtt
        snr = data.rx_snr
        hops_away = data.hops_away
        message = ""
        sender = f"{from_id}"
        node_data = self.db.get_node(from_id)
        if node_data is not None:
            if node_data.long_name is not None:
                sender = f"{node_data.long_name}"
            elif node_data.short_name is not None:
                sender = f"{node_data.short_name}"
        message = f"Pong @{sender}!"
        if via_mqtt is True:
            message = message + " Heard via MQTT."
        else:
            message = message + " Heard via LoRa radio."
        if snr is not None or (node_data is not None and node_data.snr is not None) or hops_away is not None or (node_data is not None and node_data.hops_away is not None):
            message = message + "\n"
            spacer = ""
            if snr is not None:
                message = message + spacer + f"SNR: {snr}"
                spacer = ", "
            elif node_data is not None and node_data.snr is not None:
                message = message + spacer + \
                    f"Previously observed SNR: {node_data.snr}"
                spacer = ", "
            if hops_away is not None:
                message = message + spacer + f"Hops away: {hops_away}"
            elif node_data is not None and node_data.hops_away is not None:
                message = message + spacer + \
                    f"Previously observed hops away: {node_data.hops_away}"
        self.mesh_service.send_reply(message, data)

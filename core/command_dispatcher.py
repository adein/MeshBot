import os
import importlib.util
import logging

from dataclasses import dataclass
from interfaces.bot_command import BotCommand

@dataclass
class CommandData:
    __slots__ = ['sender_id', 'receiver_id', 'parameters', 'raw_message', 'channel', 'rx_time', 'rx_snr', 'hops_away', 'via_mqtt']
    sender_id: str
    receiver_id: str
    parameters: [str]
    raw_message: str
    channel: int
    rx_time: int
    rx_snr: float
    hops_away: int
    via_mqtt: bool

class CommandDispatcher:
    def __init__(self, global_services, commands_dir="./commands", my_node=None):
        self.services = global_services
        self.commands_dir = commands_dir
        self.my_node_id = my_node
        self.event_bus = self.services.get('bus')
        self.registry = {} 
        self.logger = logging.getLogger("Core.CommandDispatcher")

    def load_commands(self):
        if not os.path.exists(self.commands_dir):
            os.makedirs(self.commands_dir)

        self.logger.info(f"Loading commands from {self.commands_dir}...")
        
        for filename in os.listdir(self.commands_dir):
            if filename.endswith(".py") and not filename.startswith("__"):
                self._load_file(filename)

    def _load_file(self, filename):
        module_name = filename[:-3]
        file_path = os.path.join(self.commands_dir, filename)
        
        try:
            spec = importlib.util.spec_from_file_location(module_name, file_path)
            py_mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(py_mod)

            for attr_name in dir(py_mod):
                attr = getattr(py_mod, attr_name)
                
                # 1. Must be a class subclassing BotCommand
                if (isinstance(attr, type) and 
                    issubclass(attr, BotCommand) and 
                    attr is not BotCommand):
                    
                    # Instantiate
                    cmd_instance = attr()
                    
                    # 2. Validate the attributes are strings
                    if not isinstance(cmd_instance.trigger, str) or not isinstance(cmd_instance.event_topic, str):
                        self.logger.warning(f"Skipping {attr_name}: 'trigger' or 'event_topic' is not a string.")
                        continue

                    # Register
                    self.registry[cmd_instance.trigger] = cmd_instance
                    self.logger.info(f"Registered command '!{cmd_instance.trigger}' -> {cmd_instance.event_topic}")

        except Exception as e:
            self.logger.error(f"Failed to load command file {filename}: {e}", exc_info=True)

    def start(self):
        self.event_bus.subscribe("meshtastic.text_message", self.handle_message)
        self.logger.info("Command Dispatcher started.")

    def handle_message(self, packet):
        text = packet.message.strip()
        if not text or not text.startswith('!'):
            return

        parts = text.split()
        trigger_word = parts[0][1:] 
        
        command = self.registry.get(trigger_word)
        
        if command:
            self.logger.info(f"Command recognized: !{trigger_word}")
            sender_id = packet.sender_id
            db = self.services.get('db')
            if db:
                db.log_command(trigger_word, sender_id)
            args_list = parts[1:] if len(parts) > 1 else None

            receiver_id = packet.receiver_id
            parameters = args_list
            raw_message = text
            channel = packet.channel
            rx_time = packet.rx_time
            rx_snr = packet.rx_snr
            via_mqtt = packet.via_mqtt
            hops_away = None
            if packet.hop_start != None and packet.hop_limit != None:
                hops_away = packet.hop_start - packet.hop_limit
            data = CommandData(
                sender_id,
                receiver_id,
                parameters,
                raw_message,
                channel,
                rx_time,
                rx_snr,
                hops_away,
                via_mqtt,
            )
            self.event_bus.publish(command.event_topic, data)
        else:
            self.logger.info(f"Unknown command: !{trigger_word}")

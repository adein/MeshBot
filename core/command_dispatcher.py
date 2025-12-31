from __future__ import annotations

import os
import importlib.util
import logging

from dataclasses import dataclass
from typing import TYPE_CHECKING

from core.event_bus import EventBus
from interfaces.bot_command import BotCommand
from services.meshtastic_service import TEXT_MESSAGE_TOPIC

if TYPE_CHECKING:
    from services.meshtastic_service import TextPacket

COMMANDS_DIR = "./commands"


@dataclass
class CommandData:
    """
    Data class to hold command information.
    """
    __slots__ = ['sender_id', 'receiver_id', 'parameters', 'raw_message',
                 'channel', 'rx_time', 'rx_snr', 'hops_away', 'via_mqtt']
    sender_id: str
    receiver_id: str
    parameters: list[str] | None
    raw_message: str
    channel: int | None
    rx_time: int
    rx_snr: float | None
    hops_away: int | None
    via_mqtt: bool


class CommandDispatcher:
    """
    Command Dispatcher to load and handle bot commands.
    """

    def __init__(self, global_services: dict, my_node: str):
        self.services = global_services
        self.commands_dir = COMMANDS_DIR
        self.my_node_id: str = my_node
        self.event_bus: EventBus = self.services.get('bus')
        self.registry: dict[str, BotCommand] = {}
        self.logger = logging.getLogger("Core.CommandDispatcher")

    def load_commands(self):
        """
        Load command modules from the commands directory.
        """
        if not os.path.exists(self.commands_dir):
            os.makedirs(self.commands_dir)
        self.logger.info("Loading commands from %s... ", self.commands_dir)
        for filename in os.listdir(self.commands_dir):
            if filename.endswith(".py") and not filename.startswith("__"):
                self._load_file(filename)

    def _load_file(self, filename: str):
        module_name = filename[:-3]
        file_path = os.path.join(self.commands_dir, filename)

        try:
            spec = importlib.util.spec_from_file_location(
                module_name, file_path)
            py_mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(py_mod)
            for attr_name in dir(py_mod):
                attr = getattr(py_mod, attr_name)
                # Must be a class subclassing BotCommand
                if (isinstance(attr, type) and
                    issubclass(attr, BotCommand) and
                        attr is not BotCommand):
                    cmd_instance = attr()
                    # Validate the attributes are strings
                    if not isinstance(cmd_instance.trigger, str) or not isinstance(cmd_instance.event_topic, str):
                        self.logger.warning(
                            "Skipping %s: 'trigger' or 'event_topic' is not a string.", attr_name)
                        continue
                    # Register
                    self.registry[cmd_instance.trigger] = cmd_instance
                    self.logger.info(
                        "Registered command '!%s' -> %s", cmd_instance.trigger, cmd_instance.event_topic)

        except Exception as e:
            self.logger.error(
                "Failed to load command file %s: %s", filename, e, exc_info=True)

    def start(self):
        """
        Start the command dispatcher by subscribing to the event bus.
        """
        self.event_bus.subscribe(TEXT_MESSAGE_TOPIC, self.handle_message)
        self.logger.info("Command Dispatcher started.")

    def handle_message(self, packet: TextPacket):
        """
        Handle incoming text messages and dispatch commands if recognized.

        :param packet: The incoming text message.
        :type packet: TextPacket
        """
        text = packet.message.strip()
        if not text or not text.startswith('!'):
            return
        parts = text.split()
        trigger_word = parts[0][1:]
        command = self.registry.get(trigger_word)
        if command:
            self.logger.info("Command recognized: !%s", trigger_word)
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
            if packet.hop_start is not None and packet.hop_limit is not None:
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
            self.logger.info("Unknown command: !%s", trigger_word)

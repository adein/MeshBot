from datetime import datetime

from interfaces.bot_module import BotModule
from models.command import CommandData
from models.node import NodeInfo
from utils.geo_utils import get_city_state_offline
from utils.time_utils import duration_to_str


class HighNodes(BotModule):
    """
    Command module to list nodes with the highest reported altitude.
    """

    def __init__(self, name: str, config, root_config, global_services: dict, my_node: str):
        super().__init__(name, config, root_config, global_services, my_node)
        if self.event_bus:
            self.event_bus.subscribe(
                "bot.command.highnodes", self.handle_command)

    def execute(self):
        # Triggered, so this is empty
        pass

    def handle_command(self, data: CommandData):
        if not self.is_enabled():
            self.logger.warning(
                "HighNodes command triggered, but module is disabled.")
            return
        if not self.db:
            self.logger.error(
                "HighNodes command could not access the database!")
            return
        if data.sender_id is None or (data.receiver_id is None and data.channel is None):
            self.logger.debug(
                "HighNodes command is missing essential message data")
            return
        if self.is_dm_only() and not data.is_dm:
            self.logger.debug(
                "HighNodes command received in non-DM, but module is DM-only.")
            return

        self.logger.info("Handling highnodes command.")
        results: list[NodeInfo] = self.db.get_top_nodes_by_altitude(limit=5)
        if not results:
            self.mesh_service.send_reply("No results.", data)
        else:
            results_list = []
            for node in results:
                # Handle potential None values safely
                node_id = str(
                    node.node_id) if node.node_id is not None else None
                long_name = str(
                    node.long_name) if node.long_name is not None else None
                short_name = str(
                    node.short_name) if node.short_name is not None else None
                hw_model = str(
                    node.hardware) if node.hardware is not None else None
                role = str(node.role) if node.role is not None else None
                lat = node.latitude
                lon = node.longitude
                altitude = str(
                    node.altitude) if node.altitude is not None else None
                raw_uptime = node.uptime
                raw_last_seen = node.last_heard

                if lat and lon:
                    location_str = get_city_state_offline(lat, lon)
                else:
                    location_str = None
                if raw_uptime is not None:
                    uptime_str = duration_to_str(int(raw_uptime))
                else:
                    uptime_str = None
                if raw_last_seen:
                    dt = datetime.fromtimestamp(float(raw_last_seen))
                    last_seen_str = dt.strftime("%m-%d-%y %H:%M")
                else:
                    last_seen_str = None

                name_to_show = long_name if long_name else short_name
                current_string = ""
                separater = ""
                if node_id:
                    current_string = f"🆔 {node_id}"
                    separater = ", "
                if name_to_show:
                    current_string = current_string + \
                        separater + f"✏️ {name_to_show}"
                    separater = ", "
                if hw_model:
                    current_string = current_string + \
                        separater + f"📟 {hw_model}"
                    separater = ", "
                if role:
                    current_string = current_string + \
                        separater + f"️⚙️ {role}"
                    separater = ", "
                if location_str:
                    current_string = current_string + \
                        separater + f"📍 {location_str}"
                    separater = ", "
                if altitude:
                    current_string = current_string + \
                        separater + f"⛰️ {altitude}"
                    separater = ", "
                if uptime_str:
                    current_string = current_string + \
                        separater + f"⏳ {uptime_str}"
                if last_seen_str:
                    current_string = current_string + \
                        separater + f"🕘 {last_seen_str}"
                results_list.append(current_string)
            results_string = "\n".join(results_list)
            self.mesh_service.send_reply(results_string, data)

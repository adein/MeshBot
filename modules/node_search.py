from datetime import datetime

from core.command_dispatcher import CommandData
from interfaces.bot_module import BotModule
from utils.geo_utils import get_city_state_offline


class NodeSearch(BotModule):
    """
    Command module to search for matching nodes and respond with their information.
    """

    def __init__(self, name: str, config, root_config, global_services: dict, my_node: str):
        super().__init__(name, config, root_config, global_services, my_node)
        if self.event_bus:
            self.event_bus.subscribe(
                "bot.command.nodesearch", self.handle_search_request)

    def execute(self):
        # Triggered, so this is empty
        pass

    def handle_search_request(self, data: CommandData):
        if not self.is_enabled():
            self.logger.warning(
                "NodeSearch command triggered, but module is disabled.")
            return
        if not self.db:
            self.logger.error(
                "NodeSearch command could not access the database!")
            return
        if data.sender_id is None or (data.receiver_id is None and data.channel is None):
            self.logger.debug(
                "NodeSearch command is missing essential message data")
            return

        arguments = data.parameters
        if arguments is None or len(arguments) <= 0:
            self.mesh_service.send_reply(
                "You must provide a search query.", data)
            return
        query = ' '.join(arguments)
        self.logger.info("Handling nodesearch command with query: %s", query)
        results = self.db.search_nodes(query)

        if not results:
            self.mesh_service.send_reply("No matching nodes found.", data)
        else:
            results_list = []
            for row in results:
                # Handle potential None values safely
                node_id = str(row[0]) if row[0] is not None else None
                long_name = str(row[1]) if row[1] is not None else None
                short_name = str(row[2]) if row[2] is not None else None
                hw_model = str(row[3]) if row[3] is not None else None
                role = str(row[4]) if row[4] is not None else None
                lat = row[5]
                lon = row[6]
                altitude = str(row[7]) if row[7] is not None else None
                raw_last_seen = row[12]

                if lat and lon:
                    location_str = get_city_state_offline(lat, lon)
                else:
                    location_str = None
                if raw_last_seen:
                    dt = datetime.fromtimestamp(float(raw_last_seen))
                    last_seen_str = dt.strftime("%m-%d-%y %H:%M")
                else:
                    last_seen_str = None

                name_to_show = long_name if long_name else short_name
                current_string = ""
                separater = ""
                if node_id:
                    current_string = f"🆔: {node_id}"
                    separater = ", "
                if name_to_show:
                    current_string = current_string + \
                        separater + f"✏️: {name_to_show}"
                    separater = ", "
                if hw_model:
                    current_string = current_string + \
                        separater + f"📟: {hw_model}"
                    separater = ", "
                if role:
                    current_string = current_string + \
                        separater + f"️⚙️: {role}"
                    separater = ", "
                if location_str:
                    current_string = current_string + \
                        separater + f"📍: {location_str}"
                    separater = ", "
                if altitude:
                    current_string = current_string + \
                        separater + f"⛰️: {altitude}"
                    separater = ", "
                if last_seen_str:
                    current_string = current_string + \
                        separater + f"🕘: {last_seen_str}"
                results_list.append(current_string)
            results_string = "\n".join(results_list)
            self.mesh_service.send_reply(results_string, data)

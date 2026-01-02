from datetime import datetime

from core.command_dispatcher import CommandData
from interfaces.bot_module import BotModule
from utils.geo_utils import get_city_state_offline, get_lat_lon_from_string, calculate_distance


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
                "You must provide a search query (name OR ID OR 'near city, state').", data)
            return
        query = ' '.join(arguments)
        self.logger.info("Handling nodesearch command with query: %s", query)
        is_location_search = False
        target_lat, target_lon = None, None
        if "," in query or query.lower().startswith("near "):
            search_term = query.replace("near ", "")
            self.logger.debug("Geocoding query: %s", query)
            coords = get_lat_lon_from_string(search_term)
            if coords:
                target_lat, target_lon = coords
                is_location_search = True
            else:
                self.logger.debug("Geocoding failed, trying name search...")
        if is_location_search:
            # Geo Search
            raw_results = self.db.get_nodes_near(
                target_lat, target_lon, radius_miles=10)
            # Sort by Distance (Closest first)
            results = []
            for row in raw_results:
                dist = calculate_distance(
                    target_lat, target_lon, row[5], row[6])
                if dist <= 10:
                    # Append distance to the tuple for display
                    results.append(tuple(row) + (dist,))
            results.sort(key=lambda x: x[-1])
        else:
            # Standard Text Search
            results = self.db.search_nodes(query, limit=5)
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
                if last_seen_str:
                    current_string = current_string + \
                        separater + f"🕘 {last_seen_str}"
                results_list.append(current_string)
            results_string = "\n".join(results_list)
            self.mesh_service.send_reply(results_string, data)

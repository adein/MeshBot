from datetime import datetime

from interfaces.bot_module import BotModule
from services.meshtastic_service import TextToSend
from utils.geo_utils import get_city_state_offline
from utils.geo_utils import get_city_state_online

class NodeSearch(BotModule):
    def __init__(self, name, config, global_services, my_node=None):
        super().__init__(name, config, global_services, my_node)
        if self.event_bus:
            self.event_bus.subscribe("bot.command.nodesearch", self.handle_stats_request)

    def execute(self):
        pass

    def handle_stats_request(self, data):
        if not self.is_enabled():
            return
        if not self.db:
            return
        self.logger.info(f"EVENT TRIGGERED: received node search request event with data {data}")
        if data.sender_id is None or (data.receiver_id is None and data.channel is None):
            self.logger.warn(f"NodeSearch command is missing essential message data")
            return

        from_id = data.sender_id
        to_id = data.receiver_id
        channel_num = data.channel
        arguments = data.parameters
        if arguments == None or len(arguments) <= 0:
            self._send_message("You must provide a search query.", data)
            return
        query = ' '.join(arguments)
        results = self.db.search_nodes(query)

        if not results:
            self._send_message("No matching nodes found.", data)
        else:
            #SELECT node_id, long_name, short_name, hardware, role, latitude, longitude, altitude, snr, via_mqtt, channel, hops_away, last_heard, unmessagable
            results_list = []
            for row in results:
                # Handle potential None values safely
                node_id = str(row[0] or "???")
                long_name = str(row[1] or "Unknown")
                short_name = str(row[2] or "Unknown")
                hw_model = str(row[3] or "Unknown")
                role = str(row[4] or "Unknown")
                lat = row[5]
                lon = row[6]
                altitude = str(row[7]) if row[7] is not None else "N/A"
                snr = str(row[8]) if row[8] is not None else "N/A"
                raw_mqtt = row[9]
                channel = str(row[10]) if row[10] is not None else "N/A"
                hops = str(row[11]) if row[11] is not None else "N/A"
                raw_last_seen = row[12] 
                raw_unmessagable = row[13]

                if lat and lon:
                    location_str = get_city_state_offline(lat, lon)
                else:
                    location_str = "N/A"
                if raw_mqtt == 1:
                    mqtt = "Yes"
                else:
                    mqtt = "No"
                if raw_last_seen:
                    dt = datetime.fromtimestamp(float(raw_last_seen))
                    last_seen_str = dt.strftime("%m-%d-%y %H:%M")
                else:
                    last_seen_str = "N/A"
                if raw_unmessagable == 1:
                    unmessagable = "Yes"
                else:
                    unmessagable = "No"

                name_to_show = long_name if long_name else short_name
                current_string = ""
                separater = ""
                if node_id:
                    current_string = f"ID: {node_id}"
                    separater = ", "
                if name_to_show:
                    current_string = current_string + separater + f"Name: {name_to_show}"
                    separater = ", "
                if hw_model:
                    current_string = current_string + separater + f"HW: {hw_model}"
                    separater = ", "
                if role:
                    current_string = current_string + separater + f"Role: {role}"
                    separater = ", "
                if location_str:
                    current_string = current_string + separater + f"Loc: {location_str}"
                    separater = ", "
                if altitude:
                    current_string = current_string + separater + f"Alt: {altitude}"
                    separater = ", "
                if unmessagable:
                    current_string = current_string + separater + f"Infra: {unmessagable}"
                    separater = ", "
                if last_seen_str:
                    current_string = current_string + separater + f"Seen: {last_seen_str}"
                results_list.append(current_string)
            results_string = "\n".join(results_list)[:200]
            self._send_message(results_string, data)

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
            self.logger.info(f"Node search command responding with payload: {message_data}")
            self.event_bus.publish("meshtastic_service.to_send", message_data)
        elif channel_num != None and to_id == "^all":
            message_data = TextToSend(
                    message,
                    None,
                    channel_num,
                    False
            )
            self.logger.info(f"Node search command responding with payload: {message_data}")
            self.event_bus.publish("meshtastic_service.to_send", message_data)
        else:
            self.logger.warn(f"Unable to handle node search command!")
 

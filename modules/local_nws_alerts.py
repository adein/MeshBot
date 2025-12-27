from datetime import datetime, timezone
from interfaces.bot_module import BotModule
from services.meshtastic_service import TextToSend
from services.nws_weather_service import NwsWeatherService

class NwsAlertChecker(BotModule):
    previous_alert_id = None

    def __init__(self, name, config, event_bus=None, my_node=None, mesh_svc=None):
        super().__init__(name, config, event_bus, my_node, mesh_svc)
        # Initialize the service once when the module loads
        self.api_service = NwsWeatherService()
        self.channel = self.config.get('channel', "0")

    def execute(self):
        # 1. Get configuration
        zone = self.config.get('zone', "INVALID_ZONE_ID")

        self.logger.info(f"Fetching weather alerts for zone #{zone}...")

        # 2. Call the service
        data = self.api_service.get_alerts(zone)

        # 3. Process the result
        if data == None or len(data) <= 0:
            # No alerts
            self.previous_alert_id = None
            return
        self.logger.info("NWS Alerts: {data}")
        now_utc = datetime.now(timezone.utc)
        for alert_to_process in data.reverse():
            if alert_to_process.alert_id == None:
                # Skip alerts without an ID
                continue
            elif now_utc > alert_to_process.expires:
                # Skip expired alerts
                continue
            if alert_to_process.severity.lower() in ["minor", "unknown"]:
                # Skip alerts not severe enough
                continue
            elif alert_to_process.alert_id == previous_alert_id:
                # Same alert as before and not expired
                # Return early
                return
            else:
                # Process this alert
                self_.process_alert(alert_to_process)
                return
        # No valid alerts to process, so clear state data
        self.previous_alert_id = None

    def _process_alert(self, alert):
        summary_string = "NWS Weather Alert (" + alert.severity + "): " + alert.headline
        area_string = "Areas: " + alert.areas
        description = alert.description.removeprefix('*').removeprefix(' ').removeprefix("WHAT").removeprefix('.').removeprefix('.').removeprefix('.')
        remaining_size = 200 - len(summary_string) - 1
        if description != None and len(description) > 3 and remaining_size > 20:
            message_data = TextToSend(
                    summary_string + "\n" + description[:remaining_size],
                    None,
                    channel_num
            )
            self.event_bus.publish("meshtastic_service.to_send", message_data)
        elif len(summary_string) + len(area_string) <= 199:
            message_data = TextToSend(
                    summary_string + "\n" + area_string,
                    None,
                    channel_num
            )
            self.event_bus.publish("meshtastic_service.to_send", message_data)
        elif len(summary_string) <= 200:
            message_data = TextToSend(
                    summary_string,
                    None,
                    channel_num
            )
            self.event_bus.publish("meshtastic_service.to_send", message_data)
        else:
            message_data = TextToSend(
                    summary_string[:200],
                    None,
                    channel_num
            )
            self.event_bus.publish("meshtastic_service.to_send", message_data)


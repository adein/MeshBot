from datetime import datetime, timezone
from interfaces.bot_module import BotModule
from services.meshtastic_service import TO_SEND_TOPIC, TextToSend
from services.nws_weather_service import NwsWeatherService, WeatherAlert


class NwsAlertChecker(BotModule):
    """
    Module to periodically check for NWS weather alerts and send them to a channel.
    """

    previous_alert_id: str | None = None

    def __init__(self, name: str, config, global_services: dict, my_node: str):
        super().__init__(name, config, global_services, my_node)
        # Initialize the service once when the module loads
        self.api_service = NwsWeatherService()
        self.channel: int = self.config.get('channel', 0)

    def execute(self):
        zone: str = self.config.get('zone', None)
        if zone is None:
            self.logger.warning(
                "NWS Alert Checker missing required zone configuration!")
            return
        self.logger.info("Fetching weather alerts for zone %s...", zone)
        data: list[WeatherAlert] | None = self.api_service.get_alerts(zone)
        if data is None or len(data) <= 0:
            # No alerts
            self.previous_alert_id = None
            return
        self.logger.info("NWS Alerts: %s", data)
        now_utc = datetime.now(timezone.utc)
        reversed_alerts = data[::-1]
        for alert_to_process in reversed_alerts:
            if alert_to_process.alert_id is None:
                # Skip alerts without an ID
                self.logger.warning("Skipping alert due to missing ID!")
                continue
            elif now_utc > alert_to_process.expires:
                # Skip expired alerts
                self.logger.info("Skipping expired alert")
                continue
            if alert_to_process.severity.lower() in ["minor", "unknown"]:
                # Skip alerts not severe enough
                self.logger.info("Skipping low or unknown severity alert")
                continue
            elif alert_to_process.alert_id == self.previous_alert_id:
                # Same alert as before and not expired
                # Return early
                self.logger.info("Skipping same alert as previous check")
                return
            else:
                # Process this alert
                self._process_alert(alert_to_process)
                return
        # No valid alerts to process, so clear state data
        self.previous_alert_id = None

    def _process_alert(self, alert: WeatherAlert):
        self.previous_alert_id = alert.alert_id
        summary_string = "NWS Weather Alert (" + \
            alert.severity + "): " + alert.headline
        area_string = "Areas: " + alert.areas
        description = self._process_description(alert.description)
        remaining_size = 200 - len(summary_string) - 1
        if description is not None and len(description) > 3 and remaining_size > 20:
            message_data = TextToSend(
                summary_string + "\n" + description[:remaining_size],
                None,
                self.channel,
                True
            )
            self.event_bus.publish(TO_SEND_TOPIC, message_data)
        elif len(summary_string) + len(area_string) <= 199:
            message_data = TextToSend(
                summary_string + "\n" + area_string,
                None,
                self.channel,
                True
            )
            self.event_bus.publish(TO_SEND_TOPIC, message_data)
        elif len(summary_string) <= 200:
            message_data = TextToSend(
                summary_string,
                None,
                self.channel,
                True
            )
            self.event_bus.publish(TO_SEND_TOPIC, message_data)
        else:
            message_data = TextToSend(
                summary_string[:200],
                None,
                self.channel,
                True
            )
            self.event_bus.publish(TO_SEND_TOPIC, message_data)

    def _process_description(self, description: str) -> str:
        new_description = description.replace("* WHAT...", "")
        new_description = new_description.replace("* WHERE...", "")
        new_description = new_description.replace("* WHEN...", "")
        new_description = new_description.replace("* IMPACTS...", "")
        new_description = new_description.replace(
            "* ADDITIONAL DETAILS...", "")
        new_description = new_description.replace("\n\n", "\n")
        return new_description

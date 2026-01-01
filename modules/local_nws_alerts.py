from datetime import datetime, timezone
from interfaces.bot_module import BotModule
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
        self.zone: str = self.config.get('zone', None)
        if self.zone is None:
            self.logger.error(
                "NWS Alert Checker missing required zone configuration!")

    def execute(self):
        if not self.is_enabled():
            self.logger.error(
                "NWS Alert Checker triggered, but module is disabled. This shouldn't happen.")
            return
        if self.zone is None:
            self.logger.error(
                "NWS Alert Checker missing required zone configuration!")
            return
        data: list[WeatherAlert] | None = self.api_service.get_alerts(
            self.zone)
        if data is None or len(data) <= 0:
            # No alerts
            self.previous_alert_id = None
            return
        self.logger.debug("Fetched NWS Alerts: %s", data)
        now_utc = datetime.now(timezone.utc)
        reversed_alerts = data[::-1]
        for alert_to_process in reversed_alerts:
            if alert_to_process.alert_id is None:
                # Skip alerts without an ID
                self.logger.debug("Skipping alert due to missing ID!")
                continue
            elif now_utc > alert_to_process.expires:
                # Skip expired alerts
                self.logger.debug("Skipping expired alert")
                continue
            if alert_to_process.severity.lower() in ["minor", "unknown"]:
                # Skip alerts not severe enough
                self.logger.debug("Skipping low or unknown severity alert")
                continue
            elif alert_to_process.alert_id == self.previous_alert_id:
                # Same alert as before and not expired
                # Return early
                self.logger.debug("Skipping same alert as previous check")
                return
            else:
                # Process this alert
                self._process_alert(alert_to_process)
                return
        # No valid alerts to process, so clear state data
        self.previous_alert_id = None

    def _process_alert(self, alert: WeatherAlert):
        self.logger.info("Processing alert: %s", alert)
        self.previous_alert_id = alert.alert_id
        severity_emoji = self._get_severity_emoji(alert.severity)
        summary_string = "NWS Weather Alert " + severity_emoji + ": " + alert.headline
        area_string = "Areas: " + alert.areas
        description = self._process_description(alert.description)
        remaining_size = 200 - len(summary_string) - 1
        if description is not None and len(description) > 3 and remaining_size > 20:
            message = summary_string + "\n" + description[:remaining_size]
            self.mesh_service.send_text(
                message, to_channel_number=self.channel)
        elif len(summary_string) + len(area_string) <= 199:
            message = summary_string + "\n" + area_string
            self.mesh_service.send_text(
                message, to_channel_number=self.channel)
        elif len(summary_string) <= 200:
            message = summary_string
            self.mesh_service.send_text(
                message, to_channel_number=self.channel)
        else:
            message = summary_string[:200]
            self.mesh_service.send_text(
                message, to_channel_number=self.channel)

    def _process_description(self, description: str) -> str:
        new_description = description.replace("* WHAT...", "")
        new_description = new_description.replace("* WHERE...", "")
        new_description = new_description.replace("* WHEN...", "")
        new_description = new_description.replace("* IMPACTS...", "")
        new_description = new_description.replace(
            "* ADDITIONAL DETAILS...", "")
        new_description = new_description.replace("\n\n", "\n")
        return new_description

    def _get_severity_emoji(self, severity: str) -> str:
        severity_lower = severity.lower()
        if severity_lower == "extreme" or severity_lower == "urgent":
            return "🚨"
        elif severity_lower == "severe" or severity_lower == "high" or severity_lower == "major":
            return "️❗️"
        elif severity_lower == "moderate":
            return "⚠️"
        elif severity_lower == "minor":
            return "ℹ️"
        else:
            return f"({severity})"

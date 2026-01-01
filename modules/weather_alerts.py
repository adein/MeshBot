from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from core.command_dispatcher import CommandData
from timezonefinder import TimezoneFinder
from interfaces.bot_module import BotModule
from services.positionstack_geocode_service import PositionstackGeocodeService
from services.nws_weather_service import NwsWeatherService, WeatherAlert


class WeatherAlerts(BotModule):
    """
    Module to respond to 'weather_alerts' commands with NWS weather alerts for a location.
    """

    local_tz: ZoneInfo | None = None

    def __init__(self, name: str, config, global_services: dict, my_node: str):
        super().__init__(name, config, global_services, my_node)
        # Initialize the geocode service
        self.geo_service = PositionstackGeocodeService()
        # Initialize the weather service
        self.api_service = NwsWeatherService()
        # Listen to weather summary events
        if self.event_bus:
            self.event_bus.subscribe(
                "bot.command.weather_alerts", self._handle_weather_request)

    def execute(self):
        # Triggered, so this is empty
        pass

    def _handle_weather_request(self, data: CommandData):
        if not self.is_enabled():
            self.logger.warning(
                "Alerts command triggered, but module is disabled.")
            return
        if data.sender_id is None or (data.receiver_id is None and data.channel is None):
            self.logger.debug(
                "Alerts command is missing essential message data")
            return
        # Geocode query into coordinates
        arguments = data.parameters
        self.logger.info(
            "Handling alerts command with arguments: %s", arguments)
        if arguments is None or len(arguments) <= 0:
            self.mesh_service.send_reply("You must provide a location.", data)
            return
        query = ' '.join(arguments)
        coords = self.geo_service.get_coords(query)
        if coords is None:
            self.mesh_service.send_reply(
                "Unable to identify the location for your query.", data)
            return
        localzone = self._get_time_zone(coords.latitude, coords.longitude)
        if localzone is not None:
            tz_string = self.config.get('local_timezone', localzone)
        else:
            tz_string = self.config.get(
                'local_timezone', "America/Detroit")
        self.local_tz = ZoneInfo(tz_string)
        zone = self.api_service.get_zone(coords.latitude, coords.longitude)
        if zone is None:
            self.mesh_service.send_reply(
                "Unable to identify the location for your query.", data)
            return
        alerts = self.api_service.get_alerts(zone)
        if alerts is None or len(alerts) <= 0:
            self.mesh_service.send_reply(
                "No active NWS alerts for that location.", data)
            return
        now_utc = datetime.now(timezone.utc)
        valid_alerts = []
        reversed_alerts = alerts[::-1]
        for alert_to_process in reversed_alerts:
            if now_utc > alert_to_process.expires:
                # Skip expired alerts
                continue
            if alert_to_process.severity.lower() in ["minor", "unknown"]:
                # Skip alerts not severe enough
                continue
            else:
                valid_alerts.append(alert_to_process)
        alert_summary = ""
        if len(valid_alerts) == 0:
            self.mesh_service.send_reply(
                "No active NWS alerts for that location.", data)
            return
        elif len(valid_alerts) == 1:
            alert = valid_alerts[0]
            expires_utc = alert.expires
            expires_local = expires_utc.astimezone(self.local_tz)
            expires_string = expires_local.strftime("%m/%d/%Y %I:%M %p")
            alert_emoji = self._get_severity_emoji(alert.severity)
            alert_prefix = "NWS Alert " + alert_emoji + ": "
            if len(alert_prefix) + len(alert.description) <= 200:
                alert_summary = alert_prefix + alert.description
            elif len(alert_prefix) + len(alert.headline) + 11 + len(expires_string) <= 200:
                alert_summary = alert_prefix + alert.headline + ". Expires: " + expires_string
            else:
                alert_summary = alert_prefix + alert.headline
        else:
            separater = ""
            for alert in valid_alerts:
                alert_summary = alert_summary + \
                    separater + self._process_alert(alert)
                separater = "\n"
        if len(alert_summary) <= 0:
            self.mesh_service.send_reply(
                "Error processing NWS alerts for that location.", data)
            return
        self.mesh_service.send_reply(alert_summary, data)

    def _get_time_zone(self, latitude: float, longitude: float) -> str | None:
        tf = TimezoneFinder()
        time_zone = tf.timezone_at(lat=latitude, lng=longitude)
        return time_zone

    def _process_alert(self, alert: WeatherAlert) -> str:
        expires_utc = alert.expires
        expires_local = expires_utc.astimezone(self.local_tz)
        expires_string = expires_local.strftime("%m/%d/%Y %I:%M %p")
        return alert.headline + ". Expires: " + expires_string

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

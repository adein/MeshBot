from datetime import datetime, timezone
from zoneinfo import ZoneInfo
from timezonefinder import TimezoneFinder
from interfaces.bot_module import BotModule
from services.meshtastic_service import TextToSend
from services.positionstack_geocode_service import PositionstackGeocodeService
from services.nws_weather_service import NwsWeatherService

class WeatherAlerts(BotModule):
    def __init__(self, name, config, global_services, my_node=None):
        super().__init__(name, config, global_services, my_node)
        # Initialize the geocode service
        self.geo_service = PositionstackGeocodeService()
        # Initialize the weather service
        self.api_service = NwsWeatherService()
        # Listen to weather summary events
        if self.event_bus:
            self.event_bus.subscribe("bot.command.weather_alerts", self._handle_weather_request)

    def execute(self):
        # Triggered vs scheduled, so this is empty
        pass

    def _handle_weather_request(self, data):
        if not self.is_enabled():
            return
        self.logger.info(f"EVENT TRIGGERED: received weather alerts request event with data {data}")
        if data.sender_id is None or (data.receiver_id is None and data.channel is None):
            self.logger.warn(f"Alerts command is missing essential message data")
            return
        # Geocode query into coordinates
        arguments = data.parameters
        if arguments == None or len(arguments) <= 0:
            self._send_message("You must provide a location.", data)
            return
        query = ' '.join(arguments)
        coords = self.geo_service.get_coords(query)
        if coords == None:
            self._send_message("Unable to identify the location for your query.", data)
            return
        localzone = self._get_time_zone(coords.latitude, coords.longitude)
        if localzone != None:
            self.LOCAL_TZ = self.config.get('local_timezone', localzone)
        else:
            self.LOCAL_TZ = self.config.get('local_timezone', "America/Detroit")
        self.local_tz = ZoneInfo(self.LOCAL_TZ)
        zone = self.api_service.get_zone(coords.latitude, coords.longitude)
        if zone == None:
            self._send_message("Unable to identify the location for your query.", data)
            return
        alerts = self.api_service.get_alerts(zone)
        if alerts == None or len(alerts) <= 0:
            self._send_message("No active NWS alerts for that location.", data)
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
            self._send_message("No active NWS alerts for that location.", data)
            return
        elif len(valid_alerts) == 1:
            alert = valid_alerts[0]
            expires_utc = alert.expires
            expires_local = expires_utc.astimezone(self.local_tz)
            expires_string = expires_local.strftime("%m/%d/%Y %I:%M %p")
            alert_prefix = "NWS Alert (" + alert.severity + "): "
            if len(alert_prefix) + len(alert.description) <= 200:
                alert_summary = alert_prefix + alert.description
            elif len(alert_prefix) + len(alert.headline) + 11 + len(expires_string) <= 200:
                alert_summary = alert_prefix + alert.headline + ". Expires: " + expires_string
            else:
                alert_summary = alert_prefix + alert.headline
        else:
            separater = ""
            for alert in valid_alerts:
                alert_summary = alert_summary + separater + self._process_alert(alert)
                separater = "\n"
        if len(alert_summary) <= 0:
            self._send_message("Error processing NWS alerts for that location.", data)
            return
        self._send_message(alert_summary, data)

    def _get_time_zone(self, latitude, longitude):
        tf = TimezoneFinder()
        time_zone = tf.timezone_at(lat=latitude, lng=longitude)
        return time_zone

    def _process_alert(self, alert):
        expires_utc = alert.expires
        expires_local = expires_utc.astimezone(self.local_tz)
        expires_string = expires_local.strftime("%m/%d/%Y %I:%M %p")
        return alert.headline + ". Expires: " + expires_string

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
            self.logger.info(f"Alert command responding with payload: {message_data}")
            self.event_bus.publish("meshtastic_service.to_send", message_data)
        elif channel_num != None and to_id == "^all":
            message_data = TextToSend(
                    message,
                    None,
                    channel_num,
                    False
            )
            self.logger.info(f"Alert command responding with payload: {message_data}")
            self.event_bus.publish("meshtastic_service.to_send", message_data)
        else:
            self.logger.warn(f"Unable to handle alert command!")
 

from interfaces.bot_command import BotCommand


class WeatherAlertsCommand(BotCommand):
    """
    Command that provides weather alerts for a given location.
    """
    trigger = "alerts"
    event_topic = "bot.command.weather_alerts"

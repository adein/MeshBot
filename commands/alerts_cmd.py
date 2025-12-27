from interfaces.bot_command import BotCommand

class WeatherAlertsCommand(BotCommand):
    trigger = "alerts"
    event_topic = "bot.command.weather_alerts"


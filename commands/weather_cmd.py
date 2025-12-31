from interfaces.bot_command import BotCommand


class WeatherCommand(BotCommand):
    """
    Command that provides current weather information for a given location.
    """
    trigger = "weather"
    event_topic = "bot.command.weather"

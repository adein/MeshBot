from interfaces.bot_command import BotCommand


class AirQualityCommand(BotCommand):
    """
    Command that provides air quality information for a given location.
    """
    trigger = "aqi"
    event_topic = "bot.command.air_quality"

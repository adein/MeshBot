from interfaces.bot_command import BotCommand


class ForecastCommand(BotCommand):
    """
    Command that provides weather forecast for a given location.
    """
    trigger = "forecast"
    event_topic = "bot.command.forecast"

from interfaces.bot_command import BotCommand

class ForecastCommand(BotCommand):
    trigger = "forecast"
    event_topic = "bot.command.forecast"


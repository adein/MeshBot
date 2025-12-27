from interfaces.bot_command import BotCommand

class WeatherCommand(BotCommand):
    trigger = "weather"
    event_topic = "bot.command.weather"


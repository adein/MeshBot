from interfaces.bot_command import BotCommand

class PingCommand(BotCommand):
    trigger = "ping"
    event_topic = "bot.command.ping"


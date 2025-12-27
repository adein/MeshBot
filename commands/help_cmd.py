from interfaces.bot_command import BotCommand

class HelpCommand(BotCommand):
    trigger = "help"
    event_topic = "bot.command.help"


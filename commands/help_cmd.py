from interfaces.bot_command import BotCommand


class HelpCommand(BotCommand):
    """
    Command that provides information about available commands.
    """
    trigger = "help"
    event_topic = "bot.command.help"

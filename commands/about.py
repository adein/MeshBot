from interfaces.bot_command import BotCommand


class AboutCommand(BotCommand):
    """
    Command that provides information about the bot.
    """
    trigger = "about"
    event_topic = "bot.command.about"

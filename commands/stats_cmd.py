from interfaces.bot_command import BotCommand


class StatsCommand(BotCommand):
    """
    Command that provides statistical data about the bot, channels, or users.
    """
    trigger = "stats"
    event_topic = "bot.command.stats"

from interfaces.bot_command import BotCommand


class HighNodesCommand(BotCommand):
    """
    Command that lists the nodes with the highest reported altitude.
    """
    trigger = "highnodes"
    event_topic = "bot.command.highnodes"

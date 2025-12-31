from interfaces.bot_command import BotCommand


class NodeSearchCommand(BotCommand):
    """
    Command that performs a node search operation.
    """
    trigger = "nodesearch"
    event_topic = "bot.command.nodesearch"

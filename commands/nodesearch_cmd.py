from interfaces.bot_command import BotCommand

class NodeSearchCommand(BotCommand):
    trigger = "nodesearch"
    event_topic = "bot.command.nodesearch"

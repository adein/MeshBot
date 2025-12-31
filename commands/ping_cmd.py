from interfaces.bot_command import BotCommand


class PingCommand(BotCommand):
    """
    Command that responds with 'pong' to test connectivity.
    """
    trigger = "ping"
    event_topic = "bot.command.ping"

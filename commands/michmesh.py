from interfaces.bot_command import BotCommand


class MichMeshCommand(BotCommand):
    """
    Command that provides information about the MichMesh setup.
    """
    trigger = "michmesh"
    event_topic = "bot.command.michmesh"

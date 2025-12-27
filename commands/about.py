from interfaces.bot_command import BotCommand

class AboutCommand(BotCommand):
    trigger = "about"
    event_topic = "bot.command.about"

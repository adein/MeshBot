from interfaces.bot_command import BotCommand

class StatsCommand(BotCommand):
    trigger = "stats"
    event_topic = "bot.command.stats"
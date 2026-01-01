import logging
import schedule
import time
import threading

from core.plugin_manager import PluginManager


class BotScheduler:
    """
    Background scheduler to run periodic tasks from loaded plugins.
    """

    def __init__(self, plugin_manager: PluginManager):
        self.plugin_manager: PluginManager = plugin_manager
        self.logger = logging.getLogger("Core.Scheduler")
        self.running_event: threading.Event = threading.Event()
        self.thread: threading.Thread | None = None

    def start(self):
        """Starts the background scheduler thread."""
        if self.thread and self.thread.is_alive():
            self.logger.warning("Scheduler is already running.")
            return

        self.running_event.set()
        self.thread = threading.Thread(target=self._loop, daemon=True)
        self.thread.start()
        self.logger.debug("Scheduler thread started.")

    def stop(self):
        """Signals the background thread to stop."""
        self.logger.debug("Stopping scheduler...")
        self.running_event.clear()
        if self.thread:
            self.thread.join(timeout=2)

    def reload_jobs(self):
        """Clears existing jobs and re-registers them from loaded plugins."""
        schedule.clear()
        modules = self.plugin_manager.get_all_modules()

        for name, module in modules.items():
            if module.is_enabled():
                # Default to 0s if not specified in config
                interval = module.config.get('interval_seconds', 0)

                if interval <= 0:
                    self.logger.info(
                        "Not scheduling module '%s' (Command/Event Driven)", name)
                    continue
                # Schedule the safe execution wrapper
                schedule.every(interval).seconds.do(self._safe_execute, module)
                self.logger.info(
                    "Scheduled module '%s' every %ds", name, interval)
            else:
                self.logger.info("Skipping module '%s' (Disabled)", name)

    def _safe_execute(self, module):
        """Wrapper to prevent one module crashing the whole thread."""
        try:
            module.execute()
        except Exception as e:
            self.logger.error(
                "CRITICAL: Module '%s' crashed: %s", module.name, e, exc_info=True)
            # Disable module on crash
            module.config['enabled'] = False

    def _loop(self):
        """The main loop running in the background thread."""
        while self.running_event.is_set():
            schedule.run_pending()
            time.sleep(1)

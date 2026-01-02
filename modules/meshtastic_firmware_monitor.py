from interfaces.bot_module import BotModule
from services.github_service import GitHubService, GitHubRelease


MESHTASTIC_FIRMWARE_RELEASE_DB_KEY = 'meshtastic_firmware_last_release'


class MeshtasticFirmwareMonitor(BotModule):

    def __init__(self, name: str, config, root_config, global_services: dict, my_node: str):
        super().__init__(name, config, root_config, global_services, my_node)
        # Initialize the service once when the module loads
        self.api_service = GitHubService(root_config.get(
            'services', {}).get('github_service', {}))
        self.channel: int = self.config.get('channel', 0)
        self.last_known_tag: str | None = self.db.get_state(
            MESHTASTIC_FIRMWARE_RELEASE_DB_KEY, None)

    def execute(self):
        if not self.is_enabled():
            self.logger.error(
                "Meshtastic Firmware Monitor triggered, but module is disabled. This shouldn't happen.")
            return
        release: GitHubRelease | None = self.api_service.get_latest_release()
        if release is None or release.tag_name is None:
            self.logger.debug(
                "Failed to fetch latest Meshtastic firmware release info.")
            return
        self.logger.debug(
            "Fetched latest Meshtastic firmware release: %s", release)
        latest_tag = release.tag_name
        if latest_tag == self.last_known_tag:
            self.logger.debug("No new Meshtastic firmware release found.")
            return
        # New release found
        self.logger.info(
            "New Meshtastic firmware release found: %s", latest_tag)
        # Update the stored tag in DB
        self.db.set_state(MESHTASTIC_FIRMWARE_RELEASE_DB_KEY, latest_tag)
        if self.last_known_tag is None:
            # First run, don't notify
            self.last_known_tag = latest_tag
            return
        self.last_known_tag = latest_tag
        message = f"🚀 New Meshtastic Firmware Release! Version: {latest_tag}\n{release.html_url}"
        self.mesh_service.send_text(message, to_channel_number=self.channel)

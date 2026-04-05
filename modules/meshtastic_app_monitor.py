import time

from interfaces.bot_module import BotModule
from services.github_service import GitHubService, GitHubRelease
from services.itunes_search_service import ITunesSearchService, ITunesRelease


ANDROID_REPO = "meshtastic/meshtastic-android"
IOS_BUNDLE_ID = "gvh.MeshtasticClient"
MESHTASTIC_ANDROID_APP_RELEASE_DB_KEY = 'meshtastic_android_app_last_release'
MESHTASTIC_IOS_APP_RELEASE_DB_KEY = 'meshtastic_ios_app_last_release'


class MeshtasticAppMonitor(BotModule):

    def __init__(self, name: str, config, root_config, global_services: dict, my_node: str):
        super().__init__(name, config, root_config, global_services, my_node)
        # Initialize the service once when the module loads
        self.github_service = GitHubService(root_config.get(
            'services', {}).get('github_service', {}))
        self.itunes_service = ITunesSearchService(root_config.get(
            'services', {}).get('itunes_search_service', {}))
        self.channels: list[int] = self.config.get('channels', [])
        self.last_known_android_tag: str | None = self.db.get_state(
            MESHTASTIC_ANDROID_APP_RELEASE_DB_KEY, None)
        self.last_known_ios_version: str | None = self.db.get_state(
            MESHTASTIC_IOS_APP_RELEASE_DB_KEY, None)

    def execute(self):
        if not self.is_enabled():
            self.logger.error(
                "Meshtastic App Monitor triggered, but module is disabled. This shouldn't happen.")
            return
        self._check_android()
        self._check_ios()

    def _check_android(self):
        android_release: GitHubRelease | None = self.github_service.get_latest_release(
            repo_slug=ANDROID_REPO)
        if android_release is None or android_release.tag_name is None:
            self.logger.debug(
                "Failed to fetch latest Meshtastic Android app release info.")
            return
        self.logger.debug(
            "Fetched latest Meshtastic android app release: %s", android_release)
        latest_tag = android_release.tag_name
        if latest_tag == self.last_known_android_tag:
            self.logger.debug("No new Meshtastic android app release found.")
            return
        # New release found
        self.logger.info(
            "New Meshtastic android app release found: %s", latest_tag)
        # Update the stored tag in DB
        self.db.set_state(MESHTASTIC_ANDROID_APP_RELEASE_DB_KEY, latest_tag)
        if self.last_known_android_tag is None:
            # First run, don't notify
            self.logger.info(
                "First run of android app monitor, not sending notification.")
            self.last_known_android_tag = latest_tag
            return
        self.last_known_android_tag = latest_tag
        message = f"🚀 New Meshtastic Android App Release! Version: {latest_tag}\n{android_release.html_url}"
        self._send_message(message)

    def _check_ios(self):
        ios_release: ITunesRelease | None = self.itunes_service.get_latest_app_release(
            bundle_id=IOS_BUNDLE_ID)
        if ios_release is None or ios_release.version is None:
            self.logger.debug(
                "Failed to fetch latest Meshtastic iOS app release info.")
            return
        self.logger.debug(
            "Fetched latest Meshtastic iOS app release: %s", ios_release)
        latest_version = ios_release.version
        if latest_version == self.last_known_ios_version:
            self.logger.debug("No new Meshtastic iOS app release found.")
            return
        # New release found
        self.logger.info(
            "New Meshtastic iOS app release found: %s", latest_version)
        # Update the stored version in DB
        self.db.set_state(MESHTASTIC_IOS_APP_RELEASE_DB_KEY, latest_version)
        if self.last_known_ios_version is None:
            # First run, don't notify
            self.logger.info(
                "First run of iOS app monitor, not sending notification.")
            self.last_known_ios_version = latest_version
            return
        self.last_known_ios_version = latest_version
        message = f"🚀 New Meshtastic iOS App Release! Version: {latest_version}\n{ios_release.release_notes}"
        self._send_message(message)

    def _send_message(self, message: str):
        for channel in self.channels:
            self.mesh_service.send_text(message, to_channel_number=channel)
            time.sleep(4)

import logging
import requests

from dataclasses import dataclass


BASE_URL = "https://itunes.apple.com/lookup"


@dataclass
class ITunesRelease:
    """
    Represents App Store app release metadata.
    """
    __slots__ = ['version', 'release_date', 'release_notes', 'bundle_id']
    version: str
    release_date: str
    release_notes: str
    bundle_id: str


class ITunesSearchService():
    def __init__(self, config):
        self.logger = logging.getLogger("Service.iTunesSearch")

    def get_latest_app_release(self, bundle_id: str) -> ITunesRelease | None:
        """
        Fetches the latest app release metadata from the iTunes Search API.

        :param bundle_id: The app's bundle identifier (e.g. "com.example.app")
        :type bundle_id: str
        :return: The latest app release metadata or None if not found
        :rtype: AppRelease | None
        """
        self.logger.debug(
            "Fetching latest app release for bundle ID: %s", bundle_id)
        params = {
            'bundleId': bundle_id,
        }

        try:
            response = requests.get(BASE_URL, params=params, timeout=10)
            response.raise_for_status()  # Raises HTTPError for 4xx/5xx responses

            data = response.json()
            results = data.get('results', [])
            if results and len(results) > 0:
                app_info = results[0]
                release = ITunesRelease(
                    version=app_info.get('version'),
                    release_date=app_info.get('currentVersionReleaseDate'),
                    release_notes=app_info.get('releaseNotes', ''),
                    bundle_id=app_info.get('bundleId')
                )
                return release
            else:
                self.logger.debug(
                    "No results found for bundle ID: %s", bundle_id)
                return None

        except requests.RequestException as e:
            self.logger.error(
                "Error fetching app release from iTunes Search API: %s", e)
            return None

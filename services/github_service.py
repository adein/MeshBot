
import logging
import requests

from dataclasses import dataclass


BASE_URL = "https://api.github.com"
REPO_PATH = "repos"
LATEST_RELEASE_PATH = "releases/latest"
REPO_TO_MONITOR = "meshtastic/firmware"
HEADERS = {
    'Accept': 'application/vnd.github.v3+json',
    'User-Agent': 'MeshBot/1.0'
}


@dataclass
class GitHubRelease:
    """
    Represents GitHub Release metadata.
    """
    __slots__ = ['tag_name', 'name', 'html_url', 'body', 'published_at']
    tag_name: str
    name: str
    html_url: str
    body: str
    published_at: str


class GitHubService():
    def __init__(self, config):
        self.logger = logging.getLogger("Service.GitHub")
        self.api_token = config.get('api_key')
        self.headers = HEADERS.copy()
        if self.api_token:
            self.headers['Authorization'] = f'token {self.api_token}'
            self.logger.debug("GitHub Service initialized with API Token.")
        else:
            self.logger.error("GitHub Service initialized (Anonymous mode).")

    def get_latest_release(self, repo_slug: str = REPO_TO_MONITOR) -> GitHubRelease | None:
        """
        Fetches the latest release metadata for a repo.

        :param repo_slug: The GitHub repository slug (e.g. "meshtastic/firmware")
        :type repo_slug: str
        """
        self.logger.debug(f"Fetching latest release for repo: {repo_slug}")
        url = f"{BASE_URL}/{REPO_PATH}/{repo_slug}/{LATEST_RELEASE_PATH}"

        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            response.raise_for_status()  # Raises HTTPError for 4xx/5xx responses

            data = response.json()
            if data:
                release = GitHubRelease(
                    tag_name=data.get('tag_name'),
                    name=data.get('name'),
                    html_url=data.get('html_url'),
                    body=data.get('body', ''),
                    published_at=data.get('published_at')
                )
                return release
            return None
        except requests.exceptions.Timeout:
            self.logger.error("Request timed out connecting to %s", url)
        except requests.exceptions.HTTPError as e:
            self.logger.error("HTTP Error: %s", e)
        except requests.exceptions.RequestException as e:
            self.logger.error("General Connection Error: %s", e)
        except Exception as e:
            self.logger.error(f"Failed to connect to GitHub: {e}")

        return None

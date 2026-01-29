"""Robots.txt checker using urllib.robotparser."""

from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

from lead_gen import config


def is_scraping_allowed(url: str) -> bool:
    """
    Use urllib.robotparser to check if path '/' is allowed for our user-agent.
    Returns True if allowed or if robots.txt is unreachable (fail open).
    """
    parsed = urlparse(url)
    if not parsed.scheme or not parsed.netloc:
        return False
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    rp = RobotFileParser()
    try:
        rp.set_url(robots_url)
        rp.read()
    except Exception as e:
        config.logger.debug("Could not read robots.txt for %s: %s", url, e)
        return True
    path = parsed.path if parsed.path else "/"
    if not path.startswith("/"):
        path = "/" + path
    return rp.can_fetch(config.USER_AGENT, url)

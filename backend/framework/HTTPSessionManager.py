"""
Manager for HTTP sessions with connection pooling.
"""
import logging
from typing import Dict
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from framework.RateLimitConfig import RateLimitConfig

logger = logging.getLogger(__name__)


class HTTPSessionManager:
    """
    Manager for HTTP sessions with connection pooling.
    Reuses connections for better performance.
    """

    _sessions: Dict[str, requests.Session] = {}

    @classmethod
    def getSession(cls, sessionKey: str = "default") -> requests.Session:
        """
        Get or create a session with connection pooling.

        Args:
            sessionKey: Unique key for this session (useful for different API endpoints)

        Returns:
            Configured requests.Session instance
        """
        if sessionKey not in cls._sessions:
            cls._sessions[sessionKey] = cls._createSession()

        return cls._sessions[sessionKey]

    @classmethod
    def _createSession(cls) -> requests.Session:
        """
        Create a new session with connection pooling and retry configuration.

        Returns:
            Configured requests.Session instance
        """
        session = requests.Session()

        # Configure connection pooling
        adapter = HTTPAdapter(
            pool_connections=RateLimitConfig.POOL_CONNECTIONS,
            pool_maxsize=RateLimitConfig.POOL_MAXSIZE,
            pool_block=RateLimitConfig.POOL_BLOCK,
            max_retries=Retry(
                total=0,  # We handle retries with tenacity
                connect=3,  # Only retry connection errors
                read=3,
                redirect=5,
                status_forcelist=[500, 502, 503, 504],
                raise_on_status=False
            )
        )

        session.mount('http://', adapter)
        session.mount('https://', adapter)

        logger.info(
            "RATE_LIMITER :: Created HTTP session | Pool: %d connections | Max: %d",
            RateLimitConfig.POOL_CONNECTIONS,
            RateLimitConfig.POOL_MAXSIZE
        )

        return session

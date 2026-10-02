"""
Asynchronous Python Client for Ooma Cloud (my.ooma.com).
Handles authentication, session persistence, CSRF tokens, and data extraction
for call history, voicemails, and account status.
"""

from __future__ import annotations

import asyncio
import logging
import re
from typing import Any, Dict, List, Optional
import aiohttp

_LOGGER = logging.getLogger(__name__)

BASE_URL = "https://my.ooma.com"
LOGIN_URL = f"{BASE_URL}/login"
CALL_LOGS_URL = f"{BASE_URL}/call_logs"
VOICEMAIL_URL = f"{BASE_URL}/messages"
DASHBOARD_URL = f"{BASE_URL}/dashboard"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


def clean_username(username: str) -> str:
    """Normalize phone number / username by stripping non-digit characters for 10/11 digit US numbers."""
    cleaned = username.strip()
    digits = re.sub(r"[^\d]", "", cleaned)
    if len(digits) == 11 and digits.startswith("1"):
        return digits[1:]
    elif len(digits) == 10:
        return digits
    return cleaned


class OomaError(Exception):
    """Base exception for Ooma client."""


class OomaAuthError(OomaError):
    """Authentication failure (invalid username or password)."""


class OomaConnectionError(OomaError):
    """Network or connection error communicating with Ooma."""


class OomaAPIError(OomaError):
    """Unexpected API or parsing error."""


class OomaClient:
    """Async client for interacting with Ooma Cloud portal."""

    def __init__(
        self,
        username: str,
        password: str,
        session: Optional[aiohttp.ClientSession] = None,
    ) -> None:
        self.raw_username = username.strip()
        self.username = clean_username(username)
        self.password = password
        self._session = session
        self._owns_session = session is None
        self._is_authenticated = False
        self._lock = asyncio.Lock()

    async def _get_session(self) -> aiohttp.ClientSession:
        """Always ensure an isolated session with cookie jar enabled for Ooma cookies."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                headers={"User-Agent": USER_AGENT},
                cookie_jar=aiohttp.CookieJar(unsafe=True),
            )
            self._owns_session = True
        return self._session

    async def close(self) -> None:
        """Close the underlying HTTP session if owned."""
        if self._owns_session and self._session and not self._session.closed:
            await self._session.close()

    async def __aenter__(self) -> OomaClient:
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()

    async def login(self) -> bool:
        """Authenticate with my.ooma.com using username and password."""
        async with self._lock:
            session = await self._get_session()
            _LOGGER.debug("Fetching Ooma login page to extract CSRF token for %s...", self.username)
            try:
                async with session.get(LOGIN_URL, timeout=15) as resp:
                    if resp.status != 200:
                        raise OomaConnectionError(
                            f"Failed to fetch login page: HTTP {resp.status}"
                        )
                    html = await resp.text()

                token_match = re.search(
                    r'<input[^>]*name=["\']authenticity_token["\'][^>]*value=["\']([^"\']+)["\']',
                    html,
                ) or re.search(
                    r'<meta[^>]*name=["\']csrf-token["\'][^>]*content=["\']([^"\']+)["\']',
                    html,
                )

                if not token_match:
                    raise OomaAPIError("Could not locate CSRF authenticity_token on login page")

                auth_token = token_match.group(1)
                _LOGGER.debug("Extracted CSRF token successfully")

                payload = {
                    "authenticity_token": auth_token,
                    "username": self.username,
                    "password": self.password,
                    "remember_me": "1",
                }

                headers = {
                    "Referer": LOGIN_URL,
                    "Origin": BASE_URL,
                }

                async with session.post(LOGIN_URL, data=payload, headers=headers, allow_redirects=True, timeout=20) as resp:
                    final_url = str(resp.url)
                    response_text = await resp.text()

                    # Check for invalid credentials
                    if "Invalid phone number or password" in response_text:
                        raise OomaAuthError("Invalid Ooma username or password")

                    if "/login" in final_url and ("Invalid" in response_text or "incorrect" in response_text):
                        raise OomaAuthError("Invalid Ooma username or password")

                    if resp.status not in (200, 302) and "/login" in final_url:
                        raise OomaAuthError(f"Login failed: HTTP {resp.status} at {final_url}")

                    self._is_authenticated = True
                    _LOGGER.info("Successfully authenticated with Ooma Cloud for %s", self.username)
                    return True

            except aiohttp.ClientError as err:
                raise OomaConnectionError(f"Network error during login: {err}") from err

    async def _ensure_authenticated(self) -> None:
        """Ensure the client has an active authenticated session."""
        if not self._is_authenticated:
            await self.login()

    async def get_call_logs(self, limit: int = 25) -> List[Dict[str, Any]]:
        """Fetch recent call logs (inbound, outbound, missed)."""
        await self._ensure_authenticated()
        session = await self._get_session()

        try:
            headers = {"Accept": "application/json, text/javascript, */*; q=0.01", "X-Requested-With": "XMLHttpRequest"}
            async with session.get(f"{CALL_LOGS_URL}.json", headers=headers, timeout=15) as resp:
                if resp.status == 200:
                    try:
                        data = await resp.json()
                        if isinstance(data, list):
                            return data[:limit]
                        elif isinstance(data, dict) and "call_logs" in data:
                            return data["call_logs"][:limit]
                    except Exception:
                        pass

            async with session.get(CALL_LOGS_URL, timeout=15) as resp:
                if resp.status == 401 or resp.url.path.startswith("/login"):
                    _LOGGER.warning("Session expired while fetching call logs; re-authenticating...")
                    self._is_authenticated = False
                    await self.login()
                    return await self.get_call_logs(limit)

                html = await resp.text()
                return self._parse_html_call_logs(html, limit)

        except aiohttp.ClientError as err:
            raise OomaConnectionError(f"Failed to fetch call logs: {err}") from err

    def _parse_html_call_logs(self, html: str, limit: int) -> List[Dict[str, Any]]:
        """Parse call records from the call_logs HTML table."""
        logs = []
        row_matches = re.findall(r'<tr[^>]*data-call-id=["\']?(\w+)["\']?[^>]*>(.*?)</tr>', html, re.DOTALL | re.I)
        
        for call_id, row_content in row_matches[:limit]:
            direction = "inbound"
            if "icon-call-out" in row_content or "outbound" in row_content.lower():
                direction = "outbound"
            elif "icon-call-missed" in row_content or "missed" in row_content.lower():
                direction = "missed"

            name_match = re.search(r'class=["\'][^"\']*caller-name[^"\']*["\'][^>]*>(.*?)<', row_content, re.DOTALL)
            number_match = re.search(r'class=["\'][^"\']*phone-number[^"\']*["\'][^>]*>(.*?)<', row_content, re.DOTALL)
            duration_match = re.search(r'class=["\'][^"\']*duration[^"\']*["\'][^>]*>(.*?)<', row_content, re.DOTALL)
            date_match = re.search(r'class=["\'][^"\']*date[^"\']*["\'][^>]*>(.*?)<', row_content, re.DOTALL)

            logs.append({
                "id": call_id,
                "direction": direction,
                "name": name_match.group(1).strip() if name_match else "Unknown",
                "number": number_match.group(1).strip() if number_match else "",
                "duration": duration_match.group(1).strip() if duration_match else "0:00",
                "timestamp": date_match.group(1).strip() if date_match else "",
            })
        return logs

    async def get_voicemails(self) -> Dict[str, Any]:
        """Fetch voicemail summary and list of messages."""
        await self._ensure_authenticated()
        session = await self._get_session()

        try:
            headers = {"Accept": "application/json, text/javascript, */*; q=0.01", "X-Requested-With": "XMLHttpRequest"}
            async with session.get(f"{VOICEMAIL_URL}.json", headers=headers, timeout=15) as resp:
                if resp.status == 200:
                    try:
                        return await resp.json()
                    except Exception:
                        pass

            async with session.get(VOICEMAIL_URL, timeout=15) as resp:
                if resp.status == 401 or resp.url.path.startswith("/login"):
                    self._is_authenticated = False
                    await self.login()
                    return await self.get_voicemails()

                html = await resp.text()
                return self._parse_html_voicemails(html)

        except aiohttp.ClientError as err:
            raise OomaConnectionError(f"Failed to fetch voicemails: {err}") from err

    def _parse_html_voicemails(self, html: str) -> Dict[str, Any]:
        """Parse voicemail counts and list from messages HTML."""
        unread_count = 0
        unread_matches = re.findall(r'class=["\'][^"\']*(?:unread|new-message)[^"\']*["\']', html, re.I)
        if unread_matches:
            unread_count = len(unread_matches)

        count_badge_match = re.search(r'<span[^>]*class=["\']badge[^"\']*["\'][^>]*>(\d+)</span>', html)
        if count_badge_match:
            try:
                unread_count = int(count_badge_match.group(1))
            except ValueError:
                pass

        return {
            "unread_count": unread_count,
            "total_count": unread_count,
            "messages": [],
        }

    async def get_account_summary(self) -> Dict[str, Any]:
        """Fetch general account & device status summary."""
        await self._ensure_authenticated()
        session = await self._get_session()

        try:
            async with session.get(DASHBOARD_URL, timeout=15) as resp:
                if resp.status == 401 or resp.url.path.startswith("/login"):
                    self._is_authenticated = False
                    await self.login()
                    return await self.get_account_summary()

                html = await resp.text()
                is_connected = "offline" not in html.lower() or "connected" in html.lower()
                return {
                    "connected": is_connected,
                    "service_status": "active",
                }
        except aiohttp.ClientError as err:
            raise OomaConnectionError(f"Failed to fetch account summary: {err}") from err

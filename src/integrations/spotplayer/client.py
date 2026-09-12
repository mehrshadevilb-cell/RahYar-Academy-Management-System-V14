"""
Thin HTTP client for the SpotPlayer license API.

Reference (official docs, spotplayer.ir/help/api):

    POST https://panel.spotplayer.ir/license/edit/
    Headers: Content-Type: application/json
             $API: <api key from SpotPlayer dashboard>
             $LEVEL: -1
    Body:    {"course": [...], "name": "...", "watermark": {"texts": [...]}}
    Success: {"_id": "...", "key": "...", "url": "/.../.../"}
    Error:   {"ex": {"msg": "..."}}

Only one API key is required by the real API (no separate "secret").
"""

import aiohttp

from src.integrations.spotplayer.exceptions import SpotPlayerError


LICENSE_ENDPOINT = "https://panel.spotplayer.ir/license/edit/"

# One allowed device, restricted to Windows or macOS only
# (p0 = total allowed active devices, p1 = Windows, p2 = macOS, others = 0)
DEFAULT_DEVICE_LIMITS = {
    "p0": 1,
    "p1": 1,
    "p2": 1,
    "p3": 0,
    "p4": 0,
    "p5": 0,
    "p6": 0,
}


class SpotPlayerClient:

    def __init__(self, api_key: str, timeout_seconds: int = 15):
        self.api_key = api_key
        self.timeout_seconds = timeout_seconds

    async def create_license(
        self,
        name: str,
        course_ids: list[str],
        watermark_text: str,
        test: bool = False,
    ) -> dict:
        """
        Creates a license with an unlimited lifetime (no expiry field is
        sent - the SpotPlayer panel's own default license settings decide
        that, per the official docs) restricted to a single device
        (Windows or macOS only).

        Returns {"_id": ..., "key": ..., "url": ...} on success.
        Raises SpotPlayerError on any failure.
        """

        payload = {
            "test": test,
            "course": course_ids,
            "name": name,
            "watermark": {
                "texts": [{"text": watermark_text}],
            },
            "device": DEFAULT_DEVICE_LIMITS,
        }

        headers = {
            "Content-Type": "application/json",
            "$API": self.api_key,
            "$LEVEL": "-1",
        }

        try:

            timeout = aiohttp.ClientTimeout(total=self.timeout_seconds)

            async with aiohttp.ClientSession(timeout=timeout) as session:

                async with session.post(
                    LICENSE_ENDPOINT,
                    json=payload,
                    headers=headers,
                ) as response:

                    data = await response.json(content_type=None)

        except (aiohttp.ClientError, TimeoutError) as exc:
            raise SpotPlayerError(f"خطای شبکه در ارتباط با SpotPlayer: {exc}") from exc

        if isinstance(data, dict) and data.get("ex"):
            message = data["ex"].get("msg", "خطای نامشخص از SpotPlayer")
            raise SpotPlayerError(message)

        if not isinstance(data, dict) or "_id" not in data or "key" not in data:
            raise SpotPlayerError("پاسخ نامعتبر از SpotPlayer دریافت شد.")

        return data

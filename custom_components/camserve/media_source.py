"""Media source for Camserve event clips."""

from __future__ import annotations

import logging

import aiohttp

from homeassistant.components.media_player import MediaClass, MediaType
from homeassistant.components.media_source import (
    BrowseMediaSource,
    MediaSource,
    MediaSourceItem,
    PlayMedia,
    Unresolvable,
)
from homeassistant.core import HomeAssistant

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

CATEGORY_ICONS = {
    "person": "mdi:account",
    "vehicle": "mdi:car",
    "animal": "mdi:paw",
    "package": "mdi:package-variant-closed",
    "weather": "mdi:weather-partly-cloudy",
    "unknown": "mdi:help-circle",
}


async def async_get_media_source(hass: HomeAssistant) -> CamserveMediaSource:
    """Set up Camserve media source."""
    return CamserveMediaSource(hass)


def _get_entry_data(hass: HomeAssistant) -> tuple[str, aiohttp.ClientSession] | None:
    """Get host and session from first config entry."""
    entries = hass.data.get(DOMAIN, {})
    for entry_data in entries.values():
        return entry_data["host"], entry_data["session"]
    return None


class CamserveMediaSource(MediaSource):
    """Provide Camserve event clips as a media source."""

    name = "Camserve"

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize."""
        super().__init__(DOMAIN)
        self.hass = hass

    async def async_resolve_media(self, item: MediaSourceItem) -> PlayMedia:
        """Resolve a media item to a playable URL."""
        identifier = item.identifier

        # identifier is the event_id
        if not identifier or not identifier.isdigit():
            raise Unresolvable(f"Invalid event identifier: {identifier}")

        return PlayMedia(
            url=f"/api/camserve/events/{identifier}/clip",
            mime_type="video/mp4",
        )

    async def async_browse_media(
        self, item: MediaSourceItem
    ) -> BrowseMediaSource:
        """Browse media: root → cameras → events per camera."""
        result = _get_entry_data(self.hass)
        if not result:
            raise Unresolvable("Camserve not configured")
        host, session = result

        identifier = item.identifier

        # Root level — show list of cameras
        if not identifier:
            return await self._browse_root(host, session)

        # Camera level — show recent events for this camera
        if identifier.startswith("cam"):
            return await self._browse_camera(identifier, host, session)

        raise Unresolvable(f"Unknown identifier: {identifier}")

    async def _browse_root(
        self, host: str, session: aiohttp.ClientSession
    ) -> BrowseMediaSource:
        """Build root browse listing all cameras."""
        children = []
        try:
            async with session.get(
                f"{host}/api/cameras", timeout=aiohttp.ClientTimeout(total=10)
            ) as resp:
                resp.raise_for_status()
                cameras = await resp.json()
        except (aiohttp.ClientError, TimeoutError):
            cameras = []

        for cam in cameras:
            children.append(
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=cam["id"],
                    media_class=MediaClass.DIRECTORY,
                    media_content_type=MediaType.VIDEO,
                    title=cam.get("location", cam["id"]),
                    can_play=False,
                    can_expand=True,
                    thumbnail=None,
                )
            )

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier="",
            media_class=MediaClass.DIRECTORY,
            media_content_type=MediaType.VIDEO,
            title="Camserve",
            can_play=False,
            can_expand=True,
            children=children,
        )

    async def _browse_camera(
        self, camera_id: str, host: str, session: aiohttp.ClientSession
    ) -> BrowseMediaSource:
        """List recent events for a camera."""
        children = []
        camera_label = camera_id

        try:
            async with session.get(
                f"{host}/api/events",
                params={"camera": camera_id, "limit": "50"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                resp.raise_for_status()
                data = await resp.json()
                events = data.get("events", [])
        except (aiohttp.ClientError, TimeoutError):
            events = []

        for evt in events:
            event_id = evt["id"]
            category = evt.get("classification") or "unknown"
            ts = evt.get("timestamp", "")
            desc = evt.get("vlm_description") or category.title()
            duration = evt.get("duration_sec")

            title_parts = [ts[:19].replace("T", " ")]
            if category != "unknown":
                title_parts.append(f"[{category}]")
            if duration:
                title_parts.append(f"({int(duration)}s)")

            if evt.get("camera_label"):
                camera_label = evt["camera_label"]

            children.append(
                BrowseMediaSource(
                    domain=DOMAIN,
                    identifier=str(event_id),
                    media_class=MediaClass.VIDEO,
                    media_content_type="video/mp4",
                    title=" ".join(title_parts),
                    can_play=True,
                    can_expand=False,
                    thumbnail=f"/api/camserve/events/{event_id}/thumb",
                )
            )

        return BrowseMediaSource(
            domain=DOMAIN,
            identifier=camera_id,
            media_class=MediaClass.DIRECTORY,
            media_content_type=MediaType.VIDEO,
            title=camera_label,
            can_play=False,
            can_expand=True,
            children=children,
        )

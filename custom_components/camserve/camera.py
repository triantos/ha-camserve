"""Camera platform for Camserve integration."""

from __future__ import annotations

import logging

import aiohttp

from homeassistant.components.camera import Camera, CameraEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Camserve cameras from a config entry."""
    data = hass.data[DOMAIN][entry.entry_id]
    host = data["host"]
    session = data["session"]

    try:
        async with session.get(
            f"{host}/api/cameras", timeout=aiohttp.ClientTimeout(total=10)
        ) as resp:
            resp.raise_for_status()
            cameras = await resp.json()
    except (aiohttp.ClientError, TimeoutError) as err:
        _LOGGER.error("Failed to fetch camera list: %s", err)
        return

    entities = [
        CamserveCamera(entry, cam, host, session)
        for cam in cameras
    ]
    async_add_entities(entities, update_before_add=True)


class CamserveCamera(Camera):
    """Representation of a Camserve camera."""

    _attr_has_entity_name = True
    _attr_supported_features = CameraEntityFeature.STREAM
    _attr_is_recording = True
    _attr_motion_detection_enabled = True
    _attr_brand = "Camserve"

    def __init__(
        self,
        entry: ConfigEntry,
        cam_data: dict,
        host: str,
        session: aiohttp.ClientSession,
    ) -> None:
        """Initialize the camera."""
        super().__init__()
        self._entry = entry
        self._cam_id = cam_data["id"]
        self._host = host
        self._session = session
        self._rtsp_sub = cam_data.get("rtsp_sub", "")

        self._attr_unique_id = f"camserve_{self._cam_id}"
        self._attr_name = cam_data.get("location", self._cam_id)

    @property
    def device_info(self):
        """Return device info for grouping entities."""
        return {
            "identifiers": {(DOMAIN, self._cam_id)},
            "name": f"Camserve {self._attr_name}",
            "manufacturer": "Camserve",
            "model": "IP Camera",
            "via_device": (DOMAIN, "camserve_server"),
        }

    async def stream_source(self) -> str | None:
        """Return the RTSP sub-stream URL for HA's stream component."""
        return self._rtsp_sub or None

    async def async_camera_image(
        self, width: int | None = None, height: int | None = None
    ) -> bytes | None:
        """Return a still image from the camera."""
        url = f"{self._host}/api/cameras/{self._cam_id}/snapshot"
        try:
            async with self._session.get(
                url, timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                if resp.status == 200:
                    return await resp.read()
                _LOGGER.warning(
                    "Snapshot for %s returned status %s", self._cam_id, resp.status
                )
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.warning("Snapshot for %s failed: %s", self._cam_id, err)
        return None

"""Camserve integration for Home Assistant."""

from __future__ import annotations

import logging

import aiohttp
from aiohttp import web

from homeassistant.components.http import HomeAssistantView
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, PLATFORMS

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Camserve from a config entry."""
    host = entry.data["host"]

    # Verify connectivity
    session = aiohttp.ClientSession()
    try:
        async with session.get(
            f"{host}/api/system", timeout=aiohttp.ClientTimeout(total=10)
        ) as resp:
            resp.raise_for_status()
    except (aiohttp.ClientError, TimeoutError) as err:
        await session.close()
        _LOGGER.error("Cannot connect to Camserve at %s: %s", host, err)
        return False

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {
        "host": host,
        "session": session,
    }

    # Register HTTP proxy views (idempotent — HA deduplicates by name)
    hass.http.register_view(CamserveClipProxyView(hass))
    hass.http.register_view(CamserveThumbProxyView(hass))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        data = hass.data[DOMAIN].pop(entry.entry_id)
        await data["session"].close()
    return unload_ok


def _get_host(hass: HomeAssistant) -> str | None:
    """Get the camserve host URL from the first config entry."""
    entries = hass.data.get(DOMAIN, {})
    for entry_data in entries.values():
        return entry_data["host"]
    return None


def _get_session(hass: HomeAssistant) -> aiohttp.ClientSession | None:
    """Get the shared aiohttp session."""
    entries = hass.data.get(DOMAIN, {})
    for entry_data in entries.values():
        return entry_data["session"]
    return None


class CamserveClipProxyView(HomeAssistantView):
    """Proxy event clip requests to camserve backend."""

    url = "/api/camserve/events/{event_id}/clip"
    name = "api:camserve:event_clip"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize."""
        self.hass = hass

    async def get(self, request: web.Request, event_id: str) -> web.StreamResponse:
        """Stream the MP4 clip from camserve."""
        host = _get_host(self.hass)
        session = _get_session(self.hass)
        if not host or not session:
            return web.Response(status=503, text="Camserve not configured")

        upstream_url = f"{host}/api/events/{event_id}/clip"
        try:
            async with session.get(
                upstream_url, timeout=aiohttp.ClientTimeout(total=120)
            ) as upstream:
                if upstream.status != 200:
                    return web.Response(
                        status=upstream.status,
                        text=await upstream.text(),
                    )

                response = web.StreamResponse(
                    status=200,
                    headers={
                        "Content-Type": "video/mp4",
                        "Cache-Control": "private, max-age=3600",
                    },
                )
                if upstream.content_length:
                    response.content_length = upstream.content_length
                await response.prepare(request)

                async for chunk in upstream.content.iter_chunked(64 * 1024):
                    await response.write(chunk)
                await response.write_eof()
                return response
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.error("Failed to proxy clip %s: %s", event_id, err)
            return web.Response(status=502, text="Upstream error")


class CamserveThumbProxyView(HomeAssistantView):
    """Proxy event thumbnail requests to camserve backend."""

    url = "/api/camserve/events/{event_id}/thumb"
    name = "api:camserve:event_thumb"
    requires_auth = True

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize."""
        self.hass = hass

    async def get(self, request: web.Request, event_id: str) -> web.Response:
        """Fetch and return the JPEG thumbnail from camserve."""
        host = _get_host(self.hass)
        session = _get_session(self.hass)
        if not host or not session:
            return web.Response(status=503, text="Camserve not configured")

        upstream_url = f"{host}/api/events/{event_id}/thumb"
        try:
            async with session.get(
                upstream_url, timeout=aiohttp.ClientTimeout(total=30)
            ) as upstream:
                if upstream.status != 200:
                    return web.Response(
                        status=upstream.status,
                        text=await upstream.text(),
                    )
                body = await upstream.read()
                return web.Response(
                    body=body,
                    content_type="image/jpeg",
                    headers={"Cache-Control": "private, max-age=3600"},
                )
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.error("Failed to proxy thumbnail %s: %s", event_id, err)
            return web.Response(status=502, text="Upstream error")

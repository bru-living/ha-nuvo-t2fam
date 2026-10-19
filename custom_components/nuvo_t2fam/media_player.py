"""Media player for a single FM tuner."""

import asyncio
from html import escape
import logging
import re
from urllib.parse import quote

from aiohttp import ClientError
from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .entity import NuvoEntity

_LOGGER = logging.getLogger(__name__)


def _frequency_label(frequency: float | None) -> str | None:
    """Return a compact FM frequency label for the media player card."""
    if frequency is None:
        return None
    value = f"{frequency:.2f}".rstrip("0").rstrip(".")
    return f"FM {value} MHz"


def _artwork_lines(label: str) -> list[str]:
    """Split a station name into at most three artwork lines."""
    words = label.strip().split()
    if not words:
        return ["FM RADIO"]
    lines: list[str] = []
    for word in words:
        if lines and len(lines[-1]) + len(word) + 1 <= 18:
            lines[-1] += f" {word}"
        elif len(lines) < 3:
            lines.append(word[:18])
        else:
            lines[-1] = f"{lines[-1][:15]}..."
            break
    return lines


def _station_artwork(label: str, frequency: str | None) -> bytes:
    """Create private, dependency-free station art for the media proxy."""
    safe_lines = [escape(line) for line in _artwork_lines(label)]
    start_y = 350 - ((len(safe_lines) - 1) * 48)
    text = "".join(
        f'<text x="400" y="{start_y + index * 96}" text-anchor="middle" '
        'fill="#F7F4EE" font-family="Montserrat,Arial,sans-serif" '
        f'font-size="72" font-weight="700">{line}</text>'
        for index, line in enumerate(safe_lines)
    )
    safe_frequency = escape(frequency or "FM RADIO")
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="800" height="800" viewBox="0 0 800 800">
 <defs>
  <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1"><stop stop-color="#020605"/><stop offset="1" stop-color="#0F3B32"/></linearGradient>
  <filter id="blur"><feGaussianBlur stdDeviation="65"/></filter>
 </defs>
 <rect width="800" height="800" fill="url(#bg)"/>
 <g filter="url(#blur)" opacity=".82">
  <circle cx="155" cy="145" r="210" fill="#D20A46"/>
  <circle cx="675" cy="235" r="245" fill="#D4AF37"/>
  <circle cx="385" cy="720" r="285" fill="#0F3B32"/>
 </g>
 <rect x="70" y="120" width="660" height="560" rx="48" fill="#061F1A" fill-opacity=".68" stroke="#C7A76C" stroke-opacity=".55"/>
 <text x="400" y="215" text-anchor="middle" fill="#D4AF37" font-family="Arial,sans-serif" font-size="30" font-weight="700" letter-spacing="8">NUVO</text>
 {text}
 <text x="400" y="590" text-anchor="middle" fill="#D9E2DC" font-family="Montserrat,Arial,sans-serif" font-size="34">{safe_frequency}</text>
 <text x="400" y="640" text-anchor="middle" fill="#9EAAA4" font-family="Montserrat,Arial,sans-serif" font-size="22" letter-spacing="5">BRU LIVING</text>
</svg>'''.encode()


def _normalise_station_name(value: str) -> str:
    """Normalise station names for matching RDS against directory results."""
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def _station_directory_name(value: str) -> str:
    """Remove frequency and transmitter notes before a logo-directory lookup."""
    name = re.sub(r"\s*\([^)]*\)\s*$", "", value).strip()
    name = re.sub(r"^\d{2,3}(?:\.\d+)?\s+", "", name).strip()
    name = re.sub(r"\s+\d{2,3}(?:\.\d+)?$", "", name).strip()
    return name or value.strip()


async def async_setup_entry(hass, entry, async_add_entities):
    async_add_entities([NuvoMediaPlayer(entry, hass.data[DOMAIN][entry.entry_id])])


class NuvoMediaPlayer(NuvoEntity, MediaPlayerEntity):
    _attr_name = None
    _attr_icon = "mdi:radio-fm"
    _attr_supported_features = (
        MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.PLAY_MEDIA
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
        | MediaPlayerEntityFeature.SELECT_SOURCE
    )

    def __init__(self, entry, connection):
        super().__init__(entry, connection, "media_player")
        self._station_logos: dict[str, str | None] = {}
        self._logo_url: str | None = None
        self._logo_label: str | None = None

    async def async_added_to_hass(self) -> None:
        """Start station-logo discovery when the station changes."""
        await super().async_added_to_hass()
        self.async_on_remove(
            self.connection.add_listener(self._schedule_station_logo_refresh)
        )
        self._schedule_station_logo_refresh()

    def _station_label(self) -> str | None:
        """Prefer the editable Home Assistant preset name over noisy RDS text."""
        state = self.connection.state
        local = self.connection.preset_catalog.preset_for_frequency(state.frequency)
        return (local.name if local else None) or state.station_name or state.preset_name

    def _schedule_station_logo_refresh(self) -> None:
        """Schedule a non-blocking station-logo lookup."""
        label = self._station_label()
        if label == self._logo_label:
            return
        self._logo_label = label
        self._logo_url = None
        if label:
            self.hass.async_create_task(
                self._async_refresh_station_logo(label),
                f"Find NuVo station logo for {label}",
            )

    async def _async_refresh_station_logo(self, label: str) -> None:
        """Find the closest Irish station logo in the Radio Browser directory."""
        directory_name = _station_directory_name(label)
        key = _normalise_station_name(directory_name)
        if key in self._station_logos:
            logo_url = self._station_logos[key]
        else:
            logo_url = None
            try:
                session = async_get_clientsession(self.hass)
                async with session.get(
                    "https://all.api.radio-browser.info/json/stations/search",
                    params={
                        "name": directory_name,
                        "countrycode": "IE",
                        "hidebroken": "true",
                        "order": "votes",
                        "reverse": "true",
                        "limit": 10,
                    },
                    timeout=10,
                ) as response:
                    response.raise_for_status()
                    stations = await response.json(content_type=None)
                exact = next(
                    (
                        station
                        for station in stations
                        if _normalise_station_name(str(station.get("name", ""))) == key
                        and station.get("favicon")
                    ),
                    None,
                )
                match = exact or next(
                    (station for station in stations if station.get("favicon")), None
                )
                if match:
                    candidate = str(match["favicon"])
                    if candidate.startswith(("http://", "https://")):
                        logo_url = candidate
            except (ClientError, TimeoutError, ValueError) as err:
                _LOGGER.debug("Station logo lookup failed for %s: %s", label, err)
            self._station_logos[key] = logo_url

        if self._station_label() == label:
            self._logo_url = logo_url
            self.async_write_ha_state()

    @property
    def state(self):
        if self.connection.state.powered is None:
            return None
        return (
            MediaPlayerState.PLAYING
            if self.connection.state.powered
            else MediaPlayerState.OFF
        )

    @property
    def media_title(self):
        state = self.connection.state
        local = self.connection.preset_catalog.preset_for_frequency(state.frequency)
        return (
            state.radio_text
            or state.station_name
            or (local.name if local else None)
            or state.preset_name
            or _frequency_label(state.frequency)
            or "FM radio"
        )

    @property
    def media_channel(self):
        return _frequency_label(self.connection.state.frequency)

    @property
    def media_artist(self):
        state = self.connection.state
        if state.radio_text:
            return self._station_label()
        return None

    @property
    def media_content_type(self):
        return MediaType.MUSIC

    @property
    def media_content_id(self):
        frequency = self.connection.state.frequency
        return str(frequency) if frequency is not None else None

    def _artwork_label(self) -> str:
        """Return the best stable station label for generated artwork."""
        return (
            self._station_label()
            or _frequency_label(self.connection.state.frequency)
            or "FM radio"
        )

    @property
    def media_image_url(self):
        """Trigger Home Assistant's authenticated media-image proxy."""
        if self._logo_url:
            return self._logo_url
        label = quote(self._artwork_label(), safe="")
        frequency = quote(
            _frequency_label(self.connection.state.frequency) or "", safe=""
        )
        return f"nuvo-t2fam://station/{label}?frequency={frequency}"

    async def async_get_media_image(self):
        """Return the station logo or locally generated fallback artwork."""
        if self._logo_url:
            return await super().async_get_media_image()
        state = self.connection.state
        return (
            _station_artwork(self._artwork_label(), _frequency_label(state.frequency)),
            "image/svg+xml",
        )

    def _preset_label(self, number: int) -> str:
        """Return the same friendly preset label used by the select entity."""
        name = self.connection.state.preset_names.get(number)
        return f"{number}: {name}" if name else f"Preset {number}"

    @property
    def source_list(self):
        """Expose HA-local presets, with hardware presets as a fallback."""
        local = self.connection.preset_catalog.visible_presets
        if local:
            return [preset.label for preset in local]
        return [self._preset_label(number) for number in range(1, 21)]

    @property
    def source(self):
        local = self.connection.preset_catalog.preset_for_frequency(
            self.connection.state.frequency
        )
        if local:
            return local.label
        preset = self.connection.state.preset
        return self._preset_label(preset) if preset is not None else None

    @property
    def extra_state_attributes(self):
        state = self.connection.state
        return {
            "frequency_mhz": state.frequency,
            "rds_station_name": state.station_name,
            "rds_radio_text": state.radio_text,
            "local_preset_count": len(self.connection.preset_catalog.presets),
            "station_discovery_status": self.connection.preset_catalog.status,
        }

    async def async_turn_on(self):
        _LOGGER.debug("Home Assistant power-on action received; sending *ON")
        await self.connection.send_global("ON")
        await self.connection.send("SRCFM")
        await asyncio.sleep(0.25)
        await self.connection.send("STATUS")

    async def async_turn_off(self):
        _LOGGER.debug("Home Assistant power-off action received; sending *OFF")
        await self.connection.send_global("OFF")
        await asyncio.sleep(0.25)
        await self.connection.send("STATUS")

    async def async_play_media(self, media_type, media_id, **kwargs):
        await self.connection.tune(float(media_id))

    async def async_media_next_track(self):
        if await self.connection.preset_catalog.async_step(1):
            return
        await self.connection.send("PRESET+")

    async def async_media_previous_track(self):
        if await self.connection.preset_catalog.async_step(-1):
            return
        await self.connection.send("PRESET-")

    async def async_select_source(self, source: str):
        """Tune a local discovered station or a legacy hardware preset."""
        local = self.connection.preset_catalog.preset_for_label(source)
        if local:
            await self.connection.tune(local.frequency)
            return
        number = (
            int(source.split(":", 1)[0])
            if ":" in source
            else int(source.removeprefix("Preset "))
        )
        if not 1 <= number <= 20:
            raise ValueError("Preset must be between 1 and 20")
        await self.connection.send(f"PRESET1{number}")

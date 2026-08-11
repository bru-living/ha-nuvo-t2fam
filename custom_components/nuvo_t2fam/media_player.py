"""Media player for a single FM tuner."""

import asyncio
import logging

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)

from .const import DOMAIN
from .entity import NuvoEntity

_LOGGER = logging.getLogger(__name__)


def _frequency_label(frequency: float | None) -> str | None:
    """Return a compact FM frequency label for the media player card."""
    if frequency is None:
        return None
    value = f"{frequency:.2f}".rstrip("0").rstrip(".")
    return f"FM {value} MHz"


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
        return (
            state.radio_text
            or state.station_name
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
            return state.station_name or state.preset_name
        return None

    @property
    def media_content_type(self):
        return MediaType.MUSIC

    @property
    def media_content_id(self):
        frequency = self.connection.state.frequency
        return str(frequency) if frequency is not None else None

    def _preset_label(self, number: int) -> str:
        """Return the same friendly preset label used by the select entity."""
        name = self.connection.state.preset_names.get(number)
        return f"{number}: {name}" if name else f"Preset {number}"

    @property
    def source_list(self):
        """Expose all bank-one presets in the media-player controls."""
        return [self._preset_label(number) for number in range(1, 21)]

    @property
    def source(self):
        preset = self.connection.state.preset
        return self._preset_label(preset) if preset is not None else None

    @property
    def extra_state_attributes(self):
        state = self.connection.state
        return {
            "frequency_mhz": state.frequency,
            "rds_station_name": state.station_name,
            "rds_radio_text": state.radio_text,
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
        await self.connection.send("PRESET+")

    async def async_media_previous_track(self):
        await self.connection.send("PRESET-")

    async def async_select_source(self, source: str):
        """Tune directly to the selected bank-one preset."""
        number = (
            int(source.split(":", 1)[0])
            if ":" in source
            else int(source.removeprefix("Preset "))
        )
        if not 1 <= number <= 20:
            raise ValueError("Preset must be between 1 and 20")
        await self.connection.send(f"PRESET1{number}")

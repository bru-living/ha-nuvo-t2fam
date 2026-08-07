"""NuVo NV-T2FAM ASCII protocol and reconnecting transport."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
import logging
import re

from .const import BAUD_RATE, CONNECTION_SERIAL, MAX_FREQUENCY, MIN_FREQUENCY

_LOGGER = logging.getLogger(__name__)
_FREQ_RE = re.compile(r"(?:FM|FREQ|CHAN)(\d{2,6}(?:\.\d+)?)", re.I)
_PRESET_RE = re.compile(r'^PRESET(\d{2,3})(?:,|$)', re.I)


@dataclass
class TunerState:
    """Latest known tuner state."""

    available: bool = False
    powered: bool | None = None
    frequency: float | None = None
    station_name: str | None = None
    radio_text: str | None = None
    version: str | None = None
    preset: int | None = None
    preset_name: str | None = None
    preset_names: dict[int, str] = field(default_factory=dict)
    rds_cache: dict[float, tuple[str | None, str | None]] = field(
        default_factory=dict
    )
    connected_at: str | None = None
    disconnected_at: str | None = None
    last_response_at: str | None = None
    reconnect_count: int = 0
    last_connection_error: str | None = None


class InvalidDeviceError(Exception):
    """The endpoint responded, but is not an NV-T2FAM."""


def parse_version(line: str) -> str | None:
    """Return version text from a valid NV-T2FAM version response."""
    text = line.lstrip("\x00").strip()
    if not text.upper().startswith("#VER"):
        return None
    version = text[4:].strip().strip('"').strip()
    if "NV-T2FAM" not in version.upper():
        raise InvalidDeviceError(f"Expected NV-T2FAM, received: {text}")
    return version


def normalize_frequency(value: str | float) -> float:
    """Convert common protocol/user FM frequency representations to MHz."""
    frequency = float(value)
    while frequency > MAX_FREQUENCY and frequency >= MIN_FREQUENCY * 10:
        frequency /= 10
    if not MIN_FREQUENCY <= frequency <= MAX_FREQUENCY:
        raise ValueError("FM frequency must be between 87.5 and 108.0 MHz")
    return round(frequency, 2)


def format_frequency(frequency: float) -> str:
    """Format frequency in the decimal MHz form required by the tuner."""
    text = f"{normalize_frequency(frequency):.2f}".rstrip("0")
    return text if "." in text else f"{text}.0"


def parse_response(line: str, tuner: str, state: TunerState) -> bool:
    """Apply a response belonging to the configured tuner."""
    text = line.lstrip("\x00").strip().lstrip("#")
    if text.upper() == "OFF":
        state.powered = False
        return True
    prefix = f"T'{tuner.upper()}'"
    if not text.upper().startswith(prefix):
        return False
    payload = text[len(prefix):].lstrip(" ,:=")
    upper = payload.upper()
    changed = False

    if "OFF" in upper:
        state.powered = False
        changed = True
    elif "ON" in upper or upper.startswith("FM") or upper.startswith("CHAN"):
        state.powered = True
        changed = True

    match = _FREQ_RE.search(payload.replace(" ", ""))
    if match:
        try:
            new_frequency = normalize_frequency(match.group(1))
            if state.frequency is not None and new_frequency != state.frequency:
                if state.station_name or state.radio_text:
                    state.rds_cache[state.frequency] = (
                        state.station_name,
                        state.radio_text,
                    )
                state.station_name, state.radio_text = state.rds_cache.get(
                    new_frequency, (None, None)
                )
            state.frequency = new_frequency
            changed = True
        except ValueError:
            _LOGGER.debug("Ignored out-of-range frequency in %s", line)

    preset_match = _PRESET_RE.match(payload)
    if preset_match:
        encoded = preset_match.group(1)
        bank = int(encoded[0])
        number = int(encoded[1:])
        state.preset = number if bank == 1 and 1 <= number <= 20 else None
        description = payload[preset_match.end():].strip().strip('"').strip() or None
        state.preset_name = description if state.preset is not None else None
        if state.preset is not None and description:
            state.preset_names[state.preset] = description
        changed = True

    for marker, attribute in (("TITLE", "radio_text"), ("CHAN", "station_name")):
        if upper.startswith(marker):
            value = payload[len(marker):].lstrip(" ,:=\"'").rstrip("\"'") or None
            # The tuner can transiently return empty RDS after valid data.
            # Only a real station change should clear existing metadata.
            if value is not None:
                setattr(state, attribute, value)
                if state.frequency is not None:
                    cached_name, cached_text = state.rds_cache.get(
                        state.frequency, (None, None)
                    )
                    state.rds_cache[state.frequency] = (
                        value if attribute == "station_name" else cached_name,
                        value if attribute == "radio_text" else cached_text,
                    )
                changed = True
            break
    return changed


class NuvoConnection:
    """Maintain the serial stream and dispatch status changes."""

    def __init__(self, config: dict, tuner: str, callback: Callable[[], None]) -> None:
        self.config = config
        self.tuner = tuner.upper()
        self._listeners: set[Callable[[], None]] = {callback}
        self.state = TunerState()
        self._writer = None
        self._task: asyncio.Task | None = None
        self._stopping = False
        self._write_lock = asyncio.Lock()
        self._last_write = 0.0
        self._minimum_write_gap = 0.25
        self._metadata_refresh_task: asyncio.Task | None = None

    async def start(self) -> None:
        self._stopping = False
        self._task = asyncio.create_task(self._run(), name="nuvo_t2fam_connection")

    async def stop(self) -> None:
        self._stopping = True
        if self._metadata_refresh_task:
            self._metadata_refresh_task.cancel()
        if self._task:
            self._task.cancel()
        if self._writer:
            self._writer.close()
            try:
                await self._writer.wait_closed()
            except (AttributeError, OSError):
                pass

    async def _open(self):
        import serial_asyncio_fast

        if self.config["connection_type"] == CONNECTION_SERIAL:
            port_url = self.config["serial_path"]
        else:
            port_url = f"socket://{self.config['host']}:{self.config['port']}"
        return await serial_asyncio_fast.open_serial_connection(
            url=port_url,
            baudrate=BAUD_RATE,
            bytesize=8,
            parity="N",
            stopbits=1,
            xonxoff=False,
            rtscts=False,
        )

    async def probe(self) -> str:
        """Connect and verify the endpoint identifies as an NV-T2FAM."""
        reader, writer = await asyncio.wait_for(self._open(), timeout=8)
        writer.write(b"*VER\r")
        await writer.drain()
        try:
            async with asyncio.timeout(5):
                while True:
                    response = await reader.readuntil(b"\r")
                    decoded = response.decode("ascii", errors="replace").strip()
                    if version := parse_version(decoded):
                        self.state.version = version
                        return version
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except (AttributeError, OSError):
                pass

    async def _run(self) -> None:
        delay = 1
        has_connected = False
        while not self._stopping:
            try:
                reader, self._writer = await self._open()
                if has_connected:
                    self.state.reconnect_count += 1
                has_connected = True
                self.state.available = True
                self.state.connected_at = datetime.now(timezone.utc).isoformat()
                self.state.last_connection_error = None
                self._notify()
                delay = 1
                await self.send("SRCFM")
                await self.send("STATUS")
                await self.send("CHAN")
                await self.send("TITLE")
                await self.send_global("VER")
                self._schedule_metadata_refresh()
                missed_heartbeats = 0
                while True:
                    try:
                        line = await asyncio.wait_for(reader.readuntil(b"\r"), timeout=20)
                    except asyncio.TimeoutError:
                        missed_heartbeats += 1
                        if missed_heartbeats >= 2:
                            raise ConnectionError("NuVo bridge did not answer two status heartbeats")
                        _LOGGER.debug("No data for 20 seconds; sending status heartbeat")
                        await self.send("STATUS")
                        continue
                    missed_heartbeats = 0
                    decoded = line.decode("ascii", errors="replace").lstrip("\x00").strip()
                    self.state.last_response_at = datetime.now(timezone.utc).isoformat()
                    _LOGGER.debug("Received: %s", decoded)
                    version = parse_version(decoded)
                    if version:
                        self.state.version = version
                        self._notify()
                    elif decoded.startswith("#") and parse_response(decoded, self.tuner, self.state):
                        self._notify()
            except asyncio.CancelledError:
                break
            except (
                OSError,
                ConnectionError,
                asyncio.TimeoutError,
                asyncio.IncompleteReadError,
                asyncio.LimitOverrunError,
            ) as err:
                self.state.last_connection_error = str(err)
                _LOGGER.warning("NuVo connection lost: %s; retrying in %s seconds", err, delay)
            finally:
                if self.state.available:
                    self.state.disconnected_at = datetime.now(timezone.utc).isoformat()
                self.state.available = False
                self._notify()
                self._writer = None
            await asyncio.sleep(delay)
            delay = min(delay * 2, 60)

    def command(self, action: str) -> bytes:
        return f"*T'{self.tuner}'{action}\r".encode("ascii")

    def add_listener(self, callback: Callable[[], None]) -> Callable[[], None]:
        self._listeners.add(callback)
        return lambda: self._listeners.discard(callback)

    def _notify(self) -> None:
        for callback in tuple(self._listeners):
            callback()

    async def send(self, action: str) -> None:
        if self._writer is None:
            raise ConnectionError("NuVo tuner is not connected")
        if action.startswith(("FM", "SEEK", "TUNE")):
            if self.state.frequency is not None and (
                self.state.station_name or self.state.radio_text
            ):
                self.state.rds_cache[self.state.frequency] = (
                    self.state.station_name,
                    self.state.radio_text,
                )
            self.state.preset = None
            self.state.preset_name = None
            self.state.station_name = None
            self.state.radio_text = None
            self._notify()
            self._schedule_metadata_refresh()
        elif action == "PRESET+":
            current = self.state.preset or 0
            self.state.preset = (current % 20) + 1
            self.state.preset_name = self.state.preset_names.get(self.state.preset)
            self._notify()
        elif action == "PRESET-":
            current = self.state.preset or 1
            self.state.preset = 20 if current == 1 else current - 1
            self.state.preset_name = self.state.preset_names.get(self.state.preset)
            self._notify()
        elif match := re.fullmatch(r"PRESET1(\d{1,2})", action):
            number = int(match.group(1))
            if 1 <= number <= 20:
                self.state.preset = number
                self.state.preset_name = self.state.preset_names.get(number)
                self._notify()
        if action.startswith("PRESET"):
            self._schedule_metadata_refresh()
        data = self.command(action)
        await self._write(data)

    def _schedule_metadata_refresh(self) -> None:
        """Poll RDS after a station change, allowing time for it to decode."""
        if self._metadata_refresh_task:
            self._metadata_refresh_task.cancel()
        self._metadata_refresh_task = asyncio.create_task(
            self._refresh_metadata(), name="nuvo_t2fam_rds_refresh"
        )

    async def _refresh_metadata(self) -> None:
        try:
            # Poll quickly while FM RDS settles, then progressively back off.
            # Delays are cumulative: 1, 2, 4, 7, 12, 22, 42, and 72 seconds.
            for delay in (1, 1, 2, 3, 5, 10, 20, 30):
                await asyncio.sleep(delay)
                await self.send("CHAN")
                await self.send("TITLE")
            while True:
                await asyncio.sleep(60)
                await self.send("CHAN")
                await self.send("TITLE")
        except asyncio.CancelledError:
            raise
        except (ConnectionError, OSError) as err:
            _LOGGER.debug("RDS refresh stopped because the connection was lost: %s", err)

    async def send_global(self, action: str) -> None:
        """Send one of the standalone-only global commands."""
        if self._writer is None:
            raise ConnectionError("NuVo tuner is not connected")
        data = f"*{action}\r".encode("ascii")
        await self._write(data)

    async def _write(self, data: bytes) -> None:
        """Serialize and pace writes for slower serial-over-TCP bridges."""
        async with self._write_lock:
            loop = asyncio.get_running_loop()
            remaining = self._minimum_write_gap - (loop.time() - self._last_write)
            if remaining > 0:
                await asyncio.sleep(remaining)
            if self._writer is None:
                raise ConnectionError("NuVo tuner disconnected before command was sent")
            _LOGGER.debug("Sending: %s", data.decode().strip())
            self._writer.write(data)
            await self._writer.drain()
            self._last_write = loop.time()

    async def tune(self, frequency: float) -> None:
        await self.send(f"FM{format_frequency(frequency)}")

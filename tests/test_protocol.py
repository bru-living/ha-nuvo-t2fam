"""Protocol unit tests (run with pytest)."""

import pytest

from custom_components.nuvo_t2fam.protocol import (
    InvalidDeviceError,
    NuvoConnection,
    TunerState,
    format_frequency,
    normalize_frequency,
    parse_response,
    parse_version,
)


@pytest.mark.parametrize(("raw", "expected"), [("99.9", 99.9), (101.15, 101.15)])
def test_normalize_frequency(raw, expected):
    assert normalize_frequency(raw) == expected


def test_format_frequency():
    assert format_frequency(99.9) == "99.9"
    assert format_frequency(101.15) == "101.15"


def test_tune_step_commands():
    connection = NuvoConnection({"connection_type": "serial"}, "A", lambda: None)
    assert connection.command("TUNE+") == b"*T'A'TUNE+\r"
    assert connection.command("TUNE-") == b"*T'A'TUNE-\r"


def test_parse_frequency_and_ignore_other_tuner():
    state = TunerState()
    assert parse_response("#T'A'ON,FM99.9", "A", state)
    assert state.frequency == 99.9
    assert not parse_response("#T'B'ON,FM101.7", "A", state)


def test_parse_two_digit_frequency():
    state = TunerState()
    assert parse_response("#T'A'ON,FM98.0", "A", state)
    assert state.frequency == 98.0


def test_parse_response_with_leading_nul_bytes():
    state = TunerState()
    assert parse_response("\x00\x00#T'A'CHAN\"98FM\"", "A", state)
    assert state.station_name == "98FM"


def test_parse_rds():
    state = TunerState()
    assert parse_response("#T'A'CHAN\"BBC R1\"", "A", state)
    assert parse_response("#T'A'TITLE\"Artist - Track\"", "A", state)
    assert state.station_name == "BBC R1"
    assert state.radio_text == "Artist - Track"


def test_empty_rds_does_not_erase_valid_data():
    state = TunerState(station_name="98FM", radio_text="Now playing")
    assert parse_response("#T'A'CHAN\"\"", "A", state)
    assert state.powered is True
    assert not parse_response("#T'A'TITLE\"\"", "A", state)
    assert state.station_name == "98FM"
    assert state.radio_text == "Now playing"


def test_frequency_change_clears_old_rds():
    state = TunerState(
        frequency=98.0, station_name="98FM", radio_text="Old programme"
    )
    assert parse_response("#T'A'ON,FM106.4", "A", state)
    assert state.station_name is None
    assert state.radio_text is None


def test_returning_to_frequency_restores_cached_rds():
    state = TunerState(
        frequency=98.0, station_name="98FM", radio_text="Now playing"
    )
    assert parse_response("#T'A'ON,FM106.4", "A", state)
    assert state.station_name is None
    assert parse_response("#T'A'ON,FM98.0", "A", state)
    assert state.station_name == "98FM"
    assert state.radio_text == "Now playing"


def test_new_rds_updates_frequency_cache():
    state = TunerState(frequency=102.0)
    assert parse_response('#T\'A\'CHAN"Q102"', "A", state)
    assert parse_response('#T\'A\'TITLE"Feel Good Music!"', "A", state)
    assert state.rds_cache[102.0] == ("Q102", "Feel Good Music!")


def test_parse_global_off():
    state = TunerState(powered=True)
    assert parse_response("#OFF", "A", state)
    assert state.powered is False


def test_parse_bank_one_preset():
    state = TunerState()
    assert parse_response('#T\'A\'PRESET14,"BBC Radio"', "A", state)
    assert state.preset == 4
    assert state.preset_name == "BBC Radio"
    assert state.preset_names[4] == "BBC Radio"
    assert parse_response('#T\'A\'PRESET120,"Preset Twenty"', "A", state)
    assert state.preset == 20
    assert state.preset_name == "Preset Twenty"
    assert state.preset_names[20] == "Preset Twenty"


def test_frequency_status_does_not_erase_preset():
    state = TunerState(preset=5)
    assert parse_response("#T'A'ON,FM98.0", "A", state)
    assert state.preset == 5


def test_out_of_range():
    with pytest.raises(ValueError):
        normalize_frequency(70)


def test_parse_version():
    assert parse_version("#VER NV-T2FAM FWv1.00 HWv02") == "NV-T2FAM FWv1.00 HWv02"
    assert parse_version('#VER"NV-T2FAM FWv1.18 HWv00"') == "NV-T2FAM FWv1.18 HWv00"
    with pytest.raises(InvalidDeviceError):
        parse_version("#VER NV-T2DAB FWv1.00 HWv02")


@pytest.mark.asyncio
async def test_startup_probe_requests_and_validates_version(monkeypatch):
    class Reader:
        async def readuntil(self, separator):
            assert separator == b"\r"
            return b'#VER"NV-T2FAM FWv1.18 HWv00"\r'

    class Writer:
        def __init__(self):
            self.data = b""

        def write(self, data):
            self.data += data

        async def drain(self):
            pass

        def close(self):
            pass

        async def wait_closed(self):
            pass

    writer = Writer()
    connection = NuvoConnection({"connection_type": "serial"}, "A", lambda: None)

    async def fake_open():
        return Reader(), writer

    monkeypatch.setattr(connection, "_open", fake_open)
    assert await connection.probe() == "NV-T2FAM FWv1.18 HWv00"
    assert writer.data == b"*VER\r"

"""Tests against the built-in simulator."""

from __future__ import annotations

import asyncio
import json
import socket

import pytest

from elli2modbus import (
    ChargingState,
    ElliCharger,
    ModbusConnectionError,
    ModbusExceptionResponse,
    ModbusTcpClient,
)
from elli2modbus.cli import main
from elli2modbus.simulator import ElliSim


@pytest.fixture
async def sim():
    wallbox = ElliSim()
    server = await wallbox.start("127.0.0.1", 0)
    port = server.sockets[0].getsockname()[1]
    yield wallbox, port
    server.close()
    await server.wait_closed()


def _free_port() -> int:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


# --- client ------------------------------------------------------------------


async def test_client_read_write(sim):
    wallbox, port = sim
    c = ModbusTcpClient("127.0.0.1", port)
    assert await c.read_input_registers(4) == [0x0100]
    await c.write_register(261, 100)
    assert await c.read_holding_registers(261, 2) == [100, 0]
    assert wallbox.writes == [(261, 100)]
    await c.close()


async def test_client_exception_keeps_connection(sim):
    _, port = sim
    c = ModbusTcpClient("127.0.0.1", port)
    with pytest.raises(ModbusExceptionResponse) as err:
        await c.read_input_registers(13)  # Heidelberg only, not documented by Elli
    assert err.value.code == 2
    assert await c.read_input_registers(5) == [4]
    await c.close()


async def test_client_reconnects(sim):
    _, port = sim
    c = ModbusTcpClient("127.0.0.1", port)
    await c.read_input_registers(5)
    c._writer.transport.abort()
    await asyncio.sleep(0)
    assert await c.read_input_registers(5) == [4]
    await c.close()


async def test_client_connection_refused():
    c = ModbusTcpClient("127.0.0.1", _free_port(), timeout=1)
    with pytest.raises(ModbusConnectionError):
        await c.read_input_registers(5)


# --- charger -----------------------------------------------------------------


async def test_read_info_and_status(sim):
    _, port = sim
    async with ElliCharger("127.0.0.1", port) as charger:
        info = await charger.read_info()
        assert (info.layout_version, info.min_current, info.max_current) == ("1.0.0", 6, 16)
        st = await charger.read_status()
    assert st.state is ChargingState.B1
    assert st.vehicle_connected and not st.charging and not st.problem
    assert not st.charging_allowed
    assert st.voltages == (231, 229, 232)
    assert st.pcb_temperature == 32.5
    assert st.energy_total == pytest.approx(1234.567)
    assert st.energy_since_power_on == pytest.approx(4.321)
    assert st.watchdog_timeout == 15


async def test_negative_temperature(sim):
    wallbox, port = sim
    wallbox.temp_raw = (-145) & 0xFFFF
    async with ElliCharger("127.0.0.1", port) as charger:
        assert (await charger.read_status()).pcb_temperature == -14.5


async def test_unknown_state(sim):
    wallbox, port = sim
    wallbox.state = lambda: 42
    async with ElliCharger("127.0.0.1", port) as charger:
        st = await charger.read_status()
    assert st.state is None and st.state_raw == 42 and st.problem


async def test_set_current_and_stop(sim):
    wallbox, port = sim
    async with ElliCharger("127.0.0.1", port) as charger:
        await charger.set_current(10.5)
        st = await charger.read_status()
        assert st.state is ChargingState.C2 and st.charging
        assert st.current_limit == 10.5 and st.currents == (10.5, 10.5, 10.5)
        assert st.power == round(3 * 230 * 10.5)
        await charger.stop()
        assert (await charger.read_status()).state is ChargingState.B1
    assert wallbox.writes == [(261, 105), (261, 0)]


@pytest.mark.parametrize("amps", [3, 5.9, 16.1, -1])
async def test_set_current_validates(sim, amps):
    wallbox, port = sim
    async with ElliCharger("127.0.0.1", port) as charger:
        with pytest.raises(ValueError):
            await charger.set_current(amps)
    assert wallbox.writes == []


async def test_failsafe_and_watchdog(sim):
    wallbox, port = sim
    async with ElliCharger("127.0.0.1", port) as charger:
        await charger.set_failsafe_current(6)
        await charger.set_failsafe_current(0)
        await charger.set_watchdog_timeout(30)
        with pytest.raises(ValueError):
            await charger.set_watchdog_timeout(70)
    assert wallbox.writes == [(262, 60), (262, 0), (257, 30000)]


def test_simulator_watchdog(monkeypatch):
    import time

    t = [1000.0]
    monkeypatch.setattr(time, "monotonic", lambda: t[0])
    wallbox = ElliSim()
    wallbox.holding[262] = 60
    wallbox.handle(bytes([6, 1, 5, 0, 100]))
    t[0] += 16
    wallbox.tick()
    assert wallbox.holding[261] == 60


# --- cli ---------------------------------------------------------------------


def _run_cli(port: int, *args: str) -> int:
    """Run the CLI in a worker thread (it calls asyncio.run itself)."""
    import concurrent.futures

    with concurrent.futures.ThreadPoolExecutor(1) as ex:
        return ex.submit(main, [args[0], "127.0.0.1", "--port", str(port), *args[1:]]).result()


async def test_cli(sim, capsys):
    wallbox, port = sim
    loop = asyncio.get_running_loop()
    assert await loop.run_in_executor(None, _run_cli, port, "set-current", "8") == 0
    assert wallbox.writes == [(261, 80)]
    assert "current limit 8 A" in capsys.readouterr().out

    assert await loop.run_in_executor(None, _run_cli, port, "status", "--json") == 0
    data = json.loads(capsys.readouterr().out)
    assert data["status"]["state"] == "C2"
    assert data["info"]["max_current"] == 16

    assert await loop.run_in_executor(None, _run_cli, port, "set-current", "3") == 1
    assert "must be 0 or 6-16 A" in capsys.readouterr().err


def test_cli_connection_error(capsys):
    assert main(["status", "127.0.0.1", "--port", str(_free_port())]) == 1
    assert "Modbus server enabled" in capsys.readouterr().err

"""High level API for an Elli Charger 2."""

from __future__ import annotations

from dataclasses import dataclass

from . import registers as reg
from .client import ModbusTcpClient, to_int16, to_uint32
from .registers import ChargingState


@dataclass(frozen=True)
class ChargerInfo:
    """Values that do not change during operation."""

    layout_version: str
    max_current: float  # A, from hardware config (register 100)
    min_current: float  # A, at least 6 A


@dataclass(frozen=True)
class ChargerStatus:
    """One snapshot of the wallbox."""

    state: ChargingState | None  # None if the value is not a known state
    state_raw: int
    currents: tuple[float, float, float]  # A
    voltages: tuple[int, int, int]  # V
    pcb_temperature: float  # °C
    power: int  # VA (apparent power)
    energy_since_power_on: float  # kWh (VAh / 1000)
    energy_total: float  # kWh since installation
    current_limit: float  # A, register 261 as reported (0 = blocked)
    failsafe_current: float  # A
    watchdog_timeout: float  # s, 0 = off

    @property
    def vehicle_connected(self) -> bool:
        return self.state is not None and self.state.vehicle_connected

    @property
    def charging(self) -> bool:
        return self.state is not None and self.state.charging

    @property
    def problem(self) -> bool:
        return self.state is None or self.state.problem

    @property
    def charging_allowed(self) -> bool:
        return self.current_limit > 0


def format_layout_version(raw: int) -> str:
    """0x0100 -> '1.0.0'."""
    return f"{raw >> 8}.{(raw >> 4) & 0x0F}.{raw & 0x0F}"


class ElliCharger:
    """Elli Charger 2 over Modbus TCP.

    async with ElliCharger("192.168.1.50") as charger:
        info = await charger.read_info()
        status = await charger.read_status()
        await charger.set_current(10)
    """

    def __init__(
        self,
        host: str,
        port: int = reg.DEFAULT_PORT,
        unit_id: int = reg.DEFAULT_UNIT_ID,
        timeout: float = 5.0,
    ) -> None:
        self.client = ModbusTcpClient(host, port, unit_id, timeout)
        self._info: ChargerInfo | None = None

    async def __aenter__(self) -> ElliCharger:
        return self

    async def __aexit__(self, *exc: object) -> None:
        await self.close()

    async def close(self) -> None:
        await self.client.close()

    # --- reading ----------------------------------------------------------

    async def read_info(self) -> ChargerInfo:
        (layout,) = await self.client.read_input_registers(reg.LAYOUT_VERSION, 1)
        hw_max, hw_min = await self.client.read_input_registers(reg.HW_MAX_CURRENT, 2)
        max_a = float(hw_max) if hw_max else reg.FALLBACK_MAX_CURRENT
        min_a = min(max(float(hw_min), reg.MIN_CURRENT), max_a)
        self._info = ChargerInfo(format_layout_version(layout), max_a, min_a)
        return self._info

    async def read_status(self) -> ChargerStatus:
        # Two blocks around the undocumented register 13.
        state, i1, i2, i3, temp, u1, u2, u3 = await self.client.read_input_registers(
            reg.CHARGING_STATE, 8
        )
        power, e_on_hi, e_on_lo, e_tot_hi, e_tot_lo = (
            await self.client.read_input_registers(reg.POWER, 5)
        )
        (watchdog,) = await self.client.read_holding_registers(reg.WATCHDOG_TIMEOUT, 1)
        limit, failsafe = await self.client.read_holding_registers(
            reg.MAX_CURRENT_COMMAND, 2
        )
        try:
            parsed: ChargingState | None = ChargingState(state)
        except ValueError:
            parsed = None
        return ChargerStatus(
            state=parsed,
            state_raw=state,
            currents=(i1 / 10, i2 / 10, i3 / 10),
            voltages=(u1, u2, u3),
            pcb_temperature=to_int16(temp) / 10,
            power=power,
            energy_since_power_on=to_uint32(e_on_hi, e_on_lo) / 1000,
            energy_total=to_uint32(e_tot_hi, e_tot_lo) / 1000,
            current_limit=limit / 10,
            failsafe_current=failsafe / 10,
            watchdog_timeout=watchdog / 1000,
        )

    # --- writing ----------------------------------------------------------

    async def _limits(self) -> ChargerInfo:
        return self._info or await self.read_info()

    async def _check_current(self, amps: float) -> int:
        """0 blocks charging; otherwise min..max A. Returns register value."""
        if amps == 0:
            return 0
        info = await self._limits()
        if not info.min_current <= amps <= info.max_current:
            raise ValueError(
                f"current must be 0 or {info.min_current:g}-{info.max_current:g} A, "
                f"got {amps:g}"
            )
        return round(amps * 10)

    async def set_current(self, amps: float) -> None:
        """Allow charging with up to `amps` (0.1 A resolution). 0 blocks charging."""
        await self.client.write_register(
            reg.MAX_CURRENT_COMMAND, await self._check_current(amps)
        )

    async def stop(self) -> None:
        """Block charging (current limit 0)."""
        await self.client.write_register(reg.MAX_CURRENT_COMMAND, 0)

    async def set_failsafe_current(self, amps: float) -> None:
        """Current used when Modbus traffic stops for the watchdog time. 0 = stop."""
        await self.client.write_register(
            reg.FAILSAFE_CURRENT, await self._check_current(amps)
        )

    async def set_watchdog_timeout(self, seconds: float) -> None:
        """Watchdog timeout in seconds (0 = off, max 65.535)."""
        ms = round(seconds * 1000)
        if not 0 <= ms <= reg.WATCHDOG_MAX_MS:
            raise ValueError(f"watchdog timeout must be 0-65.535 s, got {seconds:g}")
        await self.client.write_register(reg.WATCHDOG_TIMEOUT, ms)

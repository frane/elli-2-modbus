"""Simulated Elli Charger 2 Modbus TCP server, for tests and development.

Only the registers from Elli's register list exist; anything else returns
Modbus exception 2 (illegal data address), like the real device.

    elli-2-modbus simulate --port 5020
"""

from __future__ import annotations

import asyncio
import struct
import time

from .registers import HOLDING_REGISTERS as HOLDING
from .registers import INPUT_REGISTERS as INPUT


class ElliSim:
    def __init__(self, vehicle: bool = True, hw_max: int = 16, hw_min: int = 6) -> None:
        self.vehicle = vehicle
        self.hw_max = hw_max
        self.hw_min = hw_min
        self.holding = {257: 15000, 261: 0, 262: 0}
        self.energy_vah = 1_234_567  # since installation
        self.energy_on_vah = 4_321
        self.last_traffic: float | None = None
        self.watchdog_tripped = False
        self.writes: list[tuple[int, int]] = []
        self.temp_raw = 325  # 32.5 °C (int16, 0.1 °C)
        self._last_tick = time.monotonic()

    # -- physics -----------------------------------------------------------
    @property
    def charging(self) -> bool:
        return self.vehicle and self.holding[261] > 0

    @property
    def amps(self) -> float:
        return self.holding[261] / 10 if self.charging else 0.0

    def tick(self) -> None:
        now = time.monotonic()
        dt, self._last_tick = now - self._last_tick, now
        wd = self.holding[257]
        if wd and self.last_traffic is not None and (now - self.last_traffic) * 1000 > wd:
            if not self.watchdog_tripped:
                self.holding[261] = self.holding[262]
                self.watchdog_tripped = True
        vah = 3 * 230 * self.amps * dt / 3600
        self.energy_vah += round(vah)
        self.energy_on_vah += round(vah)

    def state(self) -> int:
        if not self.vehicle:
            return 3 if self.holding[261] else 2
        return 7 if self.charging else 4

    def input_value(self, reg: int) -> int:
        i = round(self.amps * 10)
        return {
            4: 0x0100,
            5: self.state(),
            6: i, 7: i, 8: i,
            9: self.temp_raw,
            10: 231, 11: 229, 12: 232,
            14: round(3 * 230 * self.amps),
            15: self.energy_on_vah >> 16, 16: self.energy_on_vah & 0xFFFF,
            17: self.energy_vah >> 16, 18: self.energy_vah & 0xFFFF,
            100: self.hw_max, 101: self.hw_min,
        }[reg]

    # -- protocol ----------------------------------------------------------
    def handle(self, pdu: bytes) -> bytes:
        self.tick()
        self.last_traffic = time.monotonic()
        self.watchdog_tripped = False
        fc = pdu[0]
        if fc in (3, 4):
            addr, count = struct.unpack(">HH", pdu[1:5])
            regs = range(addr, addr + count)
            table = HOLDING if fc == 3 else INPUT
            if not 1 <= count <= 125 or any(r not in table for r in regs):
                return bytes([fc | 0x80, 2])
            vals = [self.holding[r] if fc == 3 else self.input_value(r) for r in regs]
            return bytes([fc, 2 * count]) + struct.pack(f">{count}H", *vals)
        if fc == 6:
            addr, value = struct.unpack(">HH", pdu[1:5])
            if addr not in HOLDING:
                return bytes([fc | 0x80, 2])
            if addr in (261, 262) and not (value == 0 or 60 <= value <= self.hw_max * 10):
                return bytes([fc | 0x80, 3])
            self.holding[addr] = value
            self.writes.append((addr, value))
            return pdu[:5]
        return bytes([fc | 0x80, 1])

    async def serve_client(self, reader, writer) -> None:
        try:
            while True:
                header = await reader.readexactly(7)
                tid, _proto, length, unit = struct.unpack(">HHHB", header)
                pdu = await reader.readexactly(length - 1)
                resp = self.handle(pdu)
                writer.write(struct.pack(">HHHB", tid, 0, len(resp) + 1, unit) + resp)
                await writer.drain()
        except (asyncio.IncompleteReadError, ConnectionError):
            pass
        finally:
            writer.close()

    async def start(self, host: str = "127.0.0.1", port: int = 0) -> asyncio.Server:
        return await asyncio.start_server(self.serve_client, host, port)


async def run(host: str = "127.0.0.1", port: int = 5020, vehicle: bool = True) -> None:
    """Run the simulator until cancelled."""
    sim = ElliSim(vehicle=vehicle)
    server = await sim.start(host, port)
    print(f"Elli simulator on {host}:{port} (vehicle {'connected' if vehicle else 'absent'})")
    async with server:
        while True:
            await asyncio.sleep(1)
            sim.tick()

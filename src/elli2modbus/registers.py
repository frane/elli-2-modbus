"""Register map of Elli Charger 2 wallboxes (Elli register list v1.0).

From firmware R03.004.045.121-elli the wallbox runs a Modbus TCP server
(port 502, unit 1). Elli states the layout follows the "Ghost" platform
implementation from eSystems, i.e. the Heidelberg/Amperfied layout.
Only registers documented by Elli are listed here.
"""

from __future__ import annotations

from enum import IntEnum

DEFAULT_PORT = 502
DEFAULT_UNIT_ID = 1

# Input registers (function 0x04)
LAYOUT_VERSION = 4  # 0x0100 -> 1.0.0
CHARGING_STATE = 5  # ChargingState
CURRENT_L1 = 6  # 0.1 A rms; L2 = 7, L3 = 8
PCB_TEMPERATURE = 9  # int16, 0.1 °C
VOLTAGE_L1 = 10  # V rms; L2 = 11, L3 = 12
# 13 (Heidelberg: external lock) is not documented by Elli and never read.
POWER = 14  # VA, L1+L2+L3
ENERGY_POWER_ON = 15  # VAh, 32 bit: 15 high word, 16 low word
ENERGY_TOTAL = 17  # VAh since installation: 17 high, 18 low
HW_MAX_CURRENT = 100  # A
HW_MIN_CURRENT = 101  # A

# Holding registers (read 0x03, write 0x06)
WATCHDOG_TIMEOUT = 257  # ms, 0 = off, default 15000
MAX_CURRENT_COMMAND = 261  # 0.1 A: 0 or 60..160
FAILSAFE_CURRENT = 262  # 0.1 A: 0 or 60..160

INPUT_REGISTERS = frozenset({4, 5, 6, 7, 8, 9, 10, 11, 12, 14, 15, 16, 17, 18, 100, 101})
HOLDING_REGISTERS = frozenset({257, 261, 262})

# Firmware limits Modbus control to 16 A for now, also on 22 kW variants.
MIN_CURRENT = 6.0
FALLBACK_MAX_CURRENT = 16.0
WATCHDOG_MAX_MS = 0xFFFF


class ChargingState(IntEnum):
    """IEC 61851 based charging state (register 5)."""

    A1 = 2  # no vehicle, charging not allowed
    A2 = 3  # no vehicle, charging allowed
    B1 = 4  # vehicle connected, charging not allowed
    B2 = 5  # vehicle connected, charging allowed, not charging
    C1 = 6  # vehicle requests charging, charging not allowed
    C2 = 7  # charging
    DERATING = 8  # charging with reduced current (temperature)
    E = 9  # error state E
    F = 10  # fault state F
    ERROR = 11  # general error

    @property
    def vehicle_connected(self) -> bool:
        return self in _CONNECTED

    @property
    def charging(self) -> bool:
        return self in (ChargingState.C2, ChargingState.DERATING)

    @property
    def problem(self) -> bool:
        return self in (ChargingState.E, ChargingState.F, ChargingState.ERROR)


_CONNECTED = frozenset(
    {
        ChargingState.B1,
        ChargingState.B2,
        ChargingState.C1,
        ChargingState.C2,
        ChargingState.DERATING,
    }
)

"""Local Modbus TCP control of Elli Charger 2 wallboxes."""

from .charger import ChargerInfo, ChargerStatus, ElliCharger
from .client import (
    ModbusConnectionError,
    ModbusError,
    ModbusExceptionResponse,
    ModbusTcpClient,
)
from .registers import ChargingState

__version__ = "0.1.0"

__all__ = [
    "ChargerInfo",
    "ChargerStatus",
    "ChargingState",
    "ElliCharger",
    "ModbusConnectionError",
    "ModbusError",
    "ModbusExceptionResponse",
    "ModbusTcpClient",
    "__version__",
]

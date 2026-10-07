"""Minimal asyncio Modbus TCP client (no external dependencies).

Supports exactly what the Elli wallbox needs: read holding registers (0x03),
read input registers (0x04) and write single register (0x06). One persistent
connection, one request at a time, automatic reconnect.
"""

from __future__ import annotations

import asyncio
import struct

FC_READ_HOLDING = 0x03
FC_READ_INPUT = 0x04
FC_WRITE_SINGLE = 0x06

EXCEPTION_CODES = {
    1: "illegal function",
    2: "illegal data address",
    3: "illegal data value",
    4: "server device failure",
    6: "server device busy",
}


class ModbusError(Exception):
    """Base error."""


class ModbusConnectionError(ModbusError):
    """Connection failed, timed out or was closed."""


class ModbusExceptionResponse(ModbusError):
    """The device answered with a Modbus exception."""

    def __init__(self, function: int, code: int) -> None:
        self.function = function
        self.code = code
        text = EXCEPTION_CODES.get(code, "unknown")
        super().__init__(f"function {function:#04x}: exception {code} ({text})")


class ModbusTcpClient:
    """Async Modbus TCP client for a single unit."""

    def __init__(
        self, host: str, port: int = 502, unit_id: int = 1, timeout: float = 5.0
    ) -> None:
        self.host = host
        self.port = port
        self.unit_id = unit_id
        self.timeout = timeout
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._lock = asyncio.Lock()
        self._tid = 0

    @property
    def connected(self) -> bool:
        return self._writer is not None and not self._writer.is_closing()

    async def _open(self) -> None:
        try:
            self._reader, self._writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port), self.timeout
            )
        except (OSError, asyncio.TimeoutError) as err:
            raise ModbusConnectionError(
                f"cannot connect to {self.host}:{self.port}: {err}"
            ) from err

    async def close(self) -> None:
        writer, self._reader, self._writer = self._writer, None, None
        if writer is not None:
            writer.close()
            try:
                await writer.wait_closed()
            except (OSError, ConnectionError):
                pass

    async def _request(self, pdu: bytes) -> bytes:
        async with self._lock:
            for attempt in range(2):
                try:
                    if not self.connected:
                        await self._open()
                    return await self._transact(pdu)
                except ModbusExceptionResponse:
                    raise
                except (
                    OSError,
                    asyncio.TimeoutError,
                    asyncio.IncompleteReadError,
                    ModbusConnectionError,
                ) as err:
                    await self.close()
                    if attempt:
                        raise ModbusConnectionError(str(err) or repr(err)) from err
        raise ModbusConnectionError("unreachable")  # pragma: no cover

    async def _transact(self, pdu: bytes) -> bytes:
        assert self._reader is not None and self._writer is not None
        self._tid = (self._tid + 1) & 0xFFFF
        tid = self._tid
        self._writer.write(struct.pack(">HHHB", tid, 0, len(pdu) + 1, self.unit_id) + pdu)
        await self._writer.drain()

        while True:
            header = await asyncio.wait_for(self._reader.readexactly(7), self.timeout)
            rtid, proto, length, _unit = struct.unpack(">HHHB", header)
            if proto != 0 or not 2 <= length <= 256:
                raise ModbusConnectionError("invalid MBAP header")
            body = await asyncio.wait_for(
                self._reader.readexactly(length - 1), self.timeout
            )
            if rtid == tid:
                break
            # Late answer to an earlier, timed out request: skip it.

        function = body[0]
        if function & 0x80:
            raise ModbusExceptionResponse(function & 0x7F, body[1] if len(body) > 1 else 0)
        if function != pdu[0]:
            raise ModbusConnectionError(f"unexpected function {function:#04x}")
        return body

    async def _read(self, function: int, address: int, count: int) -> list[int]:
        body = await self._request(struct.pack(">BHH", function, address, count))
        byte_count = body[1]
        data = body[2 : 2 + byte_count]
        if byte_count != 2 * count or len(data) != byte_count:
            raise ModbusConnectionError("truncated register data")
        return list(struct.unpack(f">{count}H", data))

    async def read_input_registers(self, address: int, count: int = 1) -> list[int]:
        return await self._read(FC_READ_INPUT, address, count)

    async def read_holding_registers(self, address: int, count: int = 1) -> list[int]:
        return await self._read(FC_READ_HOLDING, address, count)

    async def write_register(self, address: int, value: int) -> None:
        if not 0 <= value <= 0xFFFF:
            raise ValueError(f"value out of range: {value}")
        pdu = struct.pack(">BHH", FC_WRITE_SINGLE, address, value)
        body = await self._request(pdu)
        if body != pdu:
            raise ModbusConnectionError("write not confirmed")


def to_int16(value: int) -> int:
    return value - 0x10000 if value & 0x8000 else value


def to_uint32(hi: int, lo: int) -> int:
    return (hi << 16) | lo

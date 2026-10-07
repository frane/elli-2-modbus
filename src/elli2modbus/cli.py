"""Command line tool: elli-2-modbus."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from dataclasses import asdict

from .charger import ElliCharger
from .client import ModbusConnectionError, ModbusError
from .registers import DEFAULT_PORT, DEFAULT_UNIT_ID

STATE_TEXT = {
    2: "A1  no vehicle (idle)",
    3: "A2  no vehicle, ready",
    4: "B1  vehicle connected, charging blocked",
    5: "B2  vehicle connected",
    6: "C1  vehicle wants to charge, charging blocked",
    7: "C2  charging",
    8: "derating (reduced current, temperature)",
    9: "E   error",
    10: "F   fault",
    11: "ERR error",
}


def _parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="elli-2-modbus",
        description="Read and control an Elli Charger 2 over Modbus TCP.",
    )
    sub = p.add_subparsers(dest="cmd", required=True)

    def target(sp: argparse.ArgumentParser) -> None:
        sp.add_argument("host", help="IP address or hostname of the wallbox")
        sp.add_argument("--port", type=int, default=DEFAULT_PORT)
        sp.add_argument("--unit", type=int, default=DEFAULT_UNIT_ID)

    sp = sub.add_parser("status", help="show all values (read only)")
    target(sp)
    sp.add_argument("--json", action="store_true", help="machine readable output")

    sp = sub.add_parser("set-current", help="allow charging with up to AMPS")
    target(sp)
    sp.add_argument("amps", type=float)

    sp = sub.add_parser("stop", help="block charging (current limit 0)")
    target(sp)

    sp = sub.add_parser("set-failsafe", help="current when Modbus traffic stops (0 = stop)")
    target(sp)
    sp.add_argument("amps", type=float)

    sp = sub.add_parser("set-watchdog", help="watchdog timeout in seconds (0 = off)")
    target(sp)
    sp.add_argument("seconds", type=float)

    sp = sub.add_parser("simulate", help="run a simulated wallbox for testing")
    sp.add_argument("--host", default="127.0.0.1")
    sp.add_argument("--port", type=int, default=5020)
    sp.add_argument("--no-vehicle", action="store_true")
    return p


async def _status(charger: ElliCharger, as_json: bool) -> None:
    info = await charger.read_info()
    st = await charger.read_status()
    if as_json:
        data = {"info": asdict(info), "status": asdict(st)}
        data["status"]["state"] = st.state.name if st.state else None
        print(json.dumps(data, indent=2))
        return
    rows = [
        ("Register layout", info.layout_version),
        ("Hardware current", f"{info.min_current:g}-{info.max_current:g} A"),
        ("State", f"{st.state_raw} = {STATE_TEXT.get(st.state_raw, 'unknown')}"),
        (
            "Current limit",
            f"{st.current_limit:g} A"
            + ("  (charging blocked)" if not st.current_limit and st.vehicle_connected else ""),
        ),
        ("Currents", " / ".join(f"{i:.1f}" for i in st.currents) + " A"),
        ("Voltages", " / ".join(str(u) for u in st.voltages) + " V"),
        ("Power", f"{st.power} VA"),
        ("Energy total", f"{st.energy_total:.3f} kWh"),
        ("Energy since boot", f"{st.energy_since_power_on:.3f} kWh"),
        ("PCB temperature", f"{st.pcb_temperature:.1f} °C"),
        ("Failsafe current", f"{st.failsafe_current:g} A"),
        ("Watchdog", f"{st.watchdog_timeout:g} s" + ("  (off)" if not st.watchdog_timeout else "")),
    ]
    for label, value in rows:
        print(f"{label:<19}{value}")


async def _run(args: argparse.Namespace) -> int:
    if args.cmd == "simulate":
        from .simulator import run

        await run(args.host, args.port, vehicle=not args.no_vehicle)
        return 0

    async with ElliCharger(args.host, args.port, args.unit) as charger:
        if args.cmd == "status":
            await _status(charger, args.json)
            return 0
        if args.cmd == "set-current":
            await charger.set_current(args.amps)
        elif args.cmd == "stop":
            await charger.stop()
        elif args.cmd == "set-failsafe":
            await charger.set_failsafe_current(args.amps)
        elif args.cmd == "set-watchdog":
            await charger.set_watchdog_timeout(args.seconds)
        st = await charger.read_status()
        print(f"ok. current limit {st.current_limit:g} A, state {STATE_TEXT.get(st.state_raw, st.state_raw)}")
        if st.watchdog_timeout and args.cmd in ("set-current", "stop"):
            print(
                f"note: without further Modbus traffic the wallbox falls back to "
                f"{st.failsafe_current:g} A after {st.watchdog_timeout:g} s"
            )
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return asyncio.run(_run(args))
    except KeyboardInterrupt:
        return 130
    except ModbusConnectionError as err:
        print(f"error: {err}", file=sys.stderr)
        print(
            "Is the Modbus server enabled in the wallbox (Verbindungen > Modbus-Server) "
            "and the address right?",
            file=sys.stderr,
        )
        return 1
    except (ModbusError, ValueError) as err:
        print(f"error: {err}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

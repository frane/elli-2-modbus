# elli-2-modbus

**English** | [Deutsch](README.de.md)

Python library and CLI for local control of **Elli Charger 2** wallboxes over **Modbus TCP**. No cloud, no EEBUS, and no dependencies.

The Home Assistant integration built on it is [ha-elli-2-modbus](https://github.com/frane/ha-elli-2-modbus).

## Supported wallboxes

Second-generation Elli wallboxes with firmware **R03.004.045.121-elli or newer** (the version that added the Modbus server):

- Elli Charger Connect 2, Pro 2, Pro 2 Eichrecht
- Volkswagen ID. Charger Connect 2 / Pro 2
- Škoda Charger Connect 2 / Pro 2
- CUPRA Charger 2 / Pro 2

Modbus runs alongside the Elli backend, so the Elli app, OCPP and firmware updates keep working.

## Enable Modbus on the wallbox

Short version (detailed guide: [docs/enable-modbus.md](docs/enable-modbus.md)):

1. Open the charger configuration in a browser at `https://<IP or hostname>`. Alternatively, connect to the wallbox hotspot and open `https://10.0.2.1`. Accept the certificate warning (**Advanced** → continue).
2. Log in as **Service User** with the service user password from the access data card.
3. **Software update**: the firmware must be **R03.004.045.121 or newer**.
4. **Connections → Modbus server**: switch it **on**. Port 502, unit ID 1.
5. Give the wallbox a fixed IP address (a DHCP reservation in your router).
6. If something else controls the current, set **Charging management → Charging settings → PV surplus charging** to **off**.
7. Test: `elli-2-modbus status <ip>`

The interface is also available in German, with the same steps: *Verbindungen → Modbus-Server*, *Ladeverwaltung → Ladeeinstellungen*.

## CLI

```bash
pip install elli-2-modbus

elli-2-modbus status 192.168.1.50          # read everything
elli-2-modbus status 192.168.1.50 --json
elli-2-modbus set-current 192.168.1.50 10  # allow charging with up to 10 A
elli-2-modbus stop 192.168.1.50            # block charging
elli-2-modbus set-failsafe 192.168.1.50 0  # what happens when Modbus traffic stops
elli-2-modbus set-watchdog 192.168.1.50 30
elli-2-modbus simulate --port 5020         # simulated wallbox for testing
```

Without installing, from the repo: `PYTHONPATH=src python3 -m elli2modbus status <ip>`

## Library

```python
from elli2modbus import ElliCharger

async with ElliCharger("192.168.1.50") as charger:
    info = await charger.read_info()      # layout version, min/max current
    status = await charger.read_status()  # state, currents, voltages, power, energy, limits
    if status.vehicle_connected:
        await charger.set_current(10)     # 0.1 A resolution
    await charger.stop()
```

The library raises three errors: `ModbusConnectionError` when the wallbox cannot be reached, `ModbusExceptionResponse` when it rejects the request, and `ValueError` when a value is out of range.

## Things to know

- **Watchdog:** if the wallbox sees no Modbus traffic for the watchdog time (default 15 s), it falls back to the failsafe current. Poll faster than that, and set the failsafe current deliberately: 0 stops charging, 6 A or more keeps charging.
- **Maximum 16 A** over Modbus for now, including the 22 kW variants. Elli has announced 32 A for a future firmware.
- **No phase switching** over Modbus.
- Register 261 can report **less than you wrote**, because the wallbox's internal limits take priority. `status.current_limit` shows the limit that is actually in effect.
- Power is reported as apparent power (VA).

Register reference: [docs/registers.md](docs/registers.md).

## Development

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[test]"
pytest
```

The simulator only implements registers from Elli's register list. Undocumented ones (for example Heidelberg's 13, 258, 259) return Modbus exception 2, like the real device.

*Not affiliated with Elli or Volkswagen Group Charging GmbH.*

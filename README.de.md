# elli-2-modbus

[English](README.md) | **Deutsch**

Python-Bibliothek und Kommandozeilen-Tool, um **Elli Charger 2** Wallboxen lokal über **Modbus TCP** zu steuern. Ohne Cloud, ohne EEBUS und ohne Abhängigkeiten.

Die Home-Assistant-Integration dazu ist [ha-elli-2-modbus](https://github.com/frane/ha-elli-2-modbus).

## Unterstützte Wallboxen

Elli-Wallboxen der zweiten Generation mit Firmware **R03.004.045.121-elli oder neuer** (seitdem gibt es den Modbus-Server):

- Elli Charger Connect 2, Pro 2, Pro 2 Eichrecht
- Volkswagen ID. Charger Connect 2 / Pro 2
- Škoda Charger Connect 2 / Pro 2
- CUPRA Charger 2 / Pro 2

Modbus läuft parallel zum Elli-Backend. Elli-App, OCPP und Firmware-Updates funktionieren also weiter.

## Modbus an der Wallbox aktivieren

Kurzfassung (ausführlich: [docs/enable-modbus.de.md](docs/enable-modbus.de.md)):

1. Wallbox-Konfiguration im Browser öffnen: `https://<IP oder Hostname>`, oder mit dem Hotspot der Wallbox verbinden und `https://10.0.2.1` öffnen. Die Zertifikatswarnung bestätigen (**Erweitert** → fortfahren).
2. Als **Service User** mit dem Service-User-Passwort von der Zugangsdatenkarte anmelden.
3. **Software-Update**: Die Firmware muss **R03.004.045.121 oder neuer** sein.
4. **Verbindungen → Modbus-Server**: **einschalten**. Port 502, Modbus-ID 1.
5. Der Wallbox eine feste IP geben (DHCP-Reservierung im Router).
6. Wenn ein anderes System den Strom regelt: **Ladeverwaltung → Ladeeinstellungen → PV-Überschuss-Laden** auf **PV-Laden aus** stellen.
7. Testen: `elli-2-modbus status <ip>`

Auf Englisch heißen die Menüs *Connections → Modbus server* und *Charging management → Charging settings*.

## Kommandozeile

```bash
pip install elli-2-modbus

elli-2-modbus status 192.168.1.50          # alles auslesen
elli-2-modbus status 192.168.1.50 --json
elli-2-modbus set-current 192.168.1.50 10  # Laden mit bis zu 10 A freigeben
elli-2-modbus stop 192.168.1.50            # Laden sperren
elli-2-modbus set-failsafe 192.168.1.50 0  # Verhalten, wenn der Modbus-Verkehr ausbleibt
elli-2-modbus set-watchdog 192.168.1.50 30
elli-2-modbus simulate --port 5020         # simulierte Wallbox zum Testen
```

Ohne Installation, direkt aus dem Repo: `PYTHONPATH=src python3 -m elli2modbus status <ip>`

## Bibliothek

```python
from elli2modbus import ElliCharger

async with ElliCharger("192.168.1.50") as charger:
    info = await charger.read_info()      # Layout-Version, min./max. Strom
    status = await charger.read_status()  # Status, Ströme, Spannungen, Leistung, Energie, Grenzen
    if status.vehicle_connected:
        await charger.set_current(10)     # Auflösung 0,1 A
    await charger.stop()
```

Die Bibliothek wirft drei Fehler: `ModbusConnectionError`, wenn die Wallbox nicht erreichbar ist, `ModbusExceptionResponse`, wenn sie die Anfrage ablehnt, und `ValueError`, wenn ein Wert außerhalb des Bereichs liegt.

## Gut zu wissen

- **Watchdog:** Sieht die Wallbox länger als die Watchdog-Zeit (Standard 15 s) keinen Modbus-Verkehr, fällt sie auf den Failsafe-Strom zurück. Deshalb häufiger abfragen und den Failsafe-Strom bewusst setzen: 0 stoppt das Laden, ab 6 A lädt sie weiter.
- **Maximal 16 A** per Modbus, auch bei den 22-kW-Varianten. Elli hat 32 A für eine künftige Firmware angekündigt.
- **Keine Phasenumschaltung** per Modbus.
- Register 261 kann **weniger zurückmelden als geschrieben**, weil die internen Grenzen der Wallbox Vorrang haben. `status.current_limit` zeigt die Grenze, die tatsächlich gilt.
- Die Leistung wird als Scheinleistung (VA) gemeldet.

Register-Referenz: [docs/registers.md](docs/registers.md).

## Entwicklung

```bash
python3 -m venv .venv && . .venv/bin/activate
pip install -e ".[test]"
pytest
```

Der Simulator kennt nur die Register aus Ellis Registerliste. Nicht dokumentierte Register (z. B. 13, 258 und 259 von Heidelberg) beantwortet er wie das echte Gerät mit Modbus-Exception 2.

*Kein offizielles Projekt von Elli oder der Volkswagen Group Charging GmbH.*

# Modbus TCP an der Elli Charger 2 aktivieren

[English](enable-modbus.md) | **Deutsch**

Gilt für Elli Charger Connect 2 / Pro 2 / Pro 2 Eichrecht, VW ID. Charger 2, Škoda Charger 2 und CUPRA Charger 2. Die Weboberfläche der Wallbox gibt es auf Deutsch und Englisch (sie richtet sich nach der Browsersprache). Menünamen stehen unten auf Deutsch, die englische Bezeichnung in Klammern.

Du brauchst die **Zugangsdatenkarte**, die bei der Wallbox lag. Darauf stehen WLAN-Name und -Passwort, der Hostname und das **Passwort für den Service User**.

## 1. Wallbox-Konfiguration öffnen

**Variante A: über das Heimnetz** (Wallbox per LAN oder WLAN verbunden)

- Im Browser im selben Netz `https://<Hostname>` (von der Karte) oder `https://<IP der Wallbox>` öffnen. Die IP findest du in der Geräteliste deines Routers.

**Variante B: über den Hotspot der Wallbox**

- Mit dem WLAN der Wallbox verbinden (SSID und Passwort von der Karte) oder den QR-Code auf der Karte scannen.
- `https://10.0.2.1` öffnen.

Der Browser warnt vor einer unsicheren Verbindung, weil die Wallbox ein selbst signiertes Zertifikat nutzt. Auf **Erweitert** (*Advanced*) klicken und fortfahren.

## 2. Als Service User anmelden

Rolle **Service User** wählen und das Service-User-Passwort von der Karte eingeben. Der Standard User darf keine Systemeinstellungen ändern.

## 3. Firmware prüfen

Unter **Software-Update** (*Software update*) steht die installierte Version. Modbus braucht **R03.004.045.121-elli oder neuer**. Ist sie älter, zuerst aktualisieren (Elli-App oder *Software-Update*).

## 4. Modbus-Server einschalten

**Verbindungen → Modbus-Server** (*Connections → Modbus server*) → **Modbus-Server** einschalten.

| Einstellung | Wert |
|---|---|
| Port | 502 |
| Modbus-ID (Unit ID) | 1 |

## 5. Feste IP-Adresse vergeben

Die IP der Wallbox im Router reservieren (DHCP-Reservierung) oder unter **Verbindungen → Ethernet** (*Connections → Ethernet*) eine statische Adresse eintragen und DHCP ausschalten. Der Client muss im selben lokalen Netz sein; über LTE funktioniert es nicht.

## 6. Eigenes PV-Überschussladen der Wallbox ausschalten

Wenn ein anderes System den Strom regelt, soll die Wallbox nicht gleichzeitig selbst regeln:

**Ladeverwaltung → Ladeeinstellungen → PV-Überschuss-Laden → PV-Laden aus** (*Charging management → Charging settings → PV surplus charging → off*).

## 7. Testen

```bash
pip install elli-2-modbus
elli-2-modbus status <IP der Wallbox>
```

Du solltest Ladestatus, Spannungen und Stromgrenze sehen. Bei `cannot connect`: Ist der Modbus-Server an, die IP richtig, und sind beide Geräte im selben Netz?

## Gut zu wissen

- Modbus läuft **zusätzlich** zum Elli-Backend. Elli-App, OCPP und Firmware-Updates funktionieren weiter.
- **Watchdog:** Sobald einmal Modbus-Verkehr stattgefunden hat, erwartet die Wallbox regelmäßigen Verkehr (Standard alle 15 s). Bleibt er aus, schaltet sie auf den **Failsafe-Strom**. Den bewusst setzen: `elli-2-modbus set-failsafe <ip> 0` stoppt das Laden, `6` lädt langsam weiter.
- **Autorisierung:** Modbus setzt die Stromgrenze. Ob ein Ladevorgang zusätzlich RFID oder App-Freigabe braucht, hängt von den Wallbox-Einstellungen ab. Für vollautomatisches Laden in der Elli-App *Sofortladen* (Laden ohne Authentifizierung) aktivieren.

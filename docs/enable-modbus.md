# Enabling Modbus TCP on an Elli Charger 2

**English** | [Deutsch](enable-modbus.de.md)

Applies to Elli Charger Connect 2 / Pro 2 / Pro 2 Eichrecht, VW ID. Charger 2, Škoda Charger 2 and CUPRA Charger 2. The wallbox web interface is available in English and German (it follows the browser language). Menu names below are English, with the German label in brackets.

You need the **card with the access data** that came with the wallbox: Wi-Fi SSID and password, hostname, and the **service user password**.

## 1. Open the charger configuration

**Option A: through your home network** (the wallbox is connected by LAN or Wi-Fi)

- In a browser on the same network, open `https://<hostname>` (hostname from the card) or `https://<IP of the wallbox>` (from your router's device list).

**Option B: through the wallbox hotspot**

- Connect to the wallbox Wi-Fi (SSID and password from the card), or scan the QR code on the card.
- Open `https://10.0.2.1`.

The browser warns about an insecure connection, because the wallbox uses a self-signed certificate. Click **Advanced** (*Erweitert*) and continue.

## 2. Log in as Service User

Choose the role **Service User** and enter the service user password from the card. The Standard User cannot change system settings.

## 3. Check the firmware

**Software update** (*Software-Update*) shows the installed version. Modbus needs **R03.004.045.121-elli or newer**. If the version is older, update first (Elli app or *Software update*).

## 4. Turn on the Modbus server

**Connections → Modbus server** (*Verbindungen → Modbus-Server*) → switch **Modbus server** on.

| Setting | Value |
|---|---|
| Port | 502 |
| Unit ID (Modbus ID) | 1 |

## 5. Give the wallbox a fixed IP address

Reserve the wallbox's IP in your router (DHCP reservation), or set a static address under **Connections → Ethernet** (*Verbindungen → Ethernet*) with DHCP turned off. The client must be on the same local network; this does not work over LTE.

## 6. Turn off the wallbox's own PV surplus charging

When something else controls the current, the wallbox should not regulate on its own at the same time:

**Charging management → Charging settings → PV surplus charging → off** (*Ladeverwaltung → Ladeeinstellungen → PV-Überschuss-Laden → PV-Laden aus*).

## 7. Test

```bash
pip install elli-2-modbus
elli-2-modbus status <IP of the wallbox>
```

You should see the charging state, voltages and the current limit. If you get `cannot connect`, check that the Modbus server is on, the IP is correct and both devices are on the same network.

## Good to know

- Modbus runs **in addition** to the Elli backend. The Elli app, OCPP and firmware updates keep working.
- **Watchdog:** once Modbus traffic has started, the wallbox expects regular traffic (default every 15 s). If traffic stops, it switches to the **failsafe current**. Set it deliberately: `elli-2-modbus set-failsafe <ip> 0` stops charging, `6` keeps charging slowly.
- **Authorization:** Modbus sets the current limit. Whether a session also needs RFID or app authorization depends on the wallbox settings. For fully automatic charging, enable instant charging (charging without authentication) in the Elli app.

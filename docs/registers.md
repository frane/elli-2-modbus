# Elli Charger 2 Modbus registers

Source: Elli "Modbus Register" list v1.0 (15 Oct 2025), valid from firmware R03.004.045.121-elli. Download: <https://www.elli.eco/de/downloads-charger2> → *Modbus Registerliste [EN]*.

Elli states that the layout follows the "Ghost" platform implementation from eSystems, which is the Heidelberg/Amperfied layout. In Elli's PDF, footnote numbers are printed directly after the addresses (e.g. `2613` = register 261, footnote 3).

Modbus TCP, port 502, unit ID 1. Big-endian, 16-bit registers.

## Input registers (FC 0x04)

| Reg | Content | Unit / encoding |
|---|---|---|
| 4 | Register layout version | 0x0100 = 1.0.0 |
| 5 | Charging state | 2=A1, 3=A2, 4=B1, 5=B2, 6=C1, 7=C2, 8=derating, 9=E, 10=F, 11=ERR |
| 6, 7, 8 | Current L1, L2, L3 rms | 0.1 A |
| 9 | PCB temperature | int16, 0.1 °C |
| 10, 11, 12 | Voltage L1, L2, L3 rms | V |
| 14 | Power L1+L2+L3 | VA |
| 15 / 16 | Energy since power-on, high / low word | VAh (high × 65536 + low) |
| 17 / 18 | Energy since installation, high / low word | VAh |
| 100 | Hardware max current | A (currently 0..16)¹ |
| 101 | Hardware min current | A¹ |

Register 13 (Heidelberg: external lock) is **not** documented by Elli and is never read.

## Holding registers (FC 0x03 read / 0x06 write)

| Reg | Content | Unit / range | Default |
|---|---|---|---|
| 257 | Modbus master watchdog timeout² | ms, 0 = off | 15000 |
| 261 | Maximal current command³ | 0.1 A: 0 or 60..160 | |
| 262 | Failsafe current (on loss of Modbus communication)⁴ | 0.1 A: 0 or 60..160 | |

Heidelberg registers 258 (standby) and 259 (remote lock) are **not** documented by Elli.

## Footnotes (Elli)

1. To correctly support the 22 kW variants, the value ranges will be extended to [0..32] in a future release.
2. The timer only starts after an initial interaction between client and server (read or write).
3. Unlike the Amperfied reference implementation, the "MaximalCurrentCommand" value can be further reduced by additional internal limit functions. Writing register 261 sets an active limit; internal automatic limits or other external EMS controls can reduce it further. A read of register 261 always shows the currently valid limit. The maximum will be raised to 32 A for the 22 kW variant.
4. The value 0 for the error state is not supported. Later, maximum values of 32 A (= 320) will be supported here as well, for the 22 kW variant.

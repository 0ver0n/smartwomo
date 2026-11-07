# QA-REPORT · Victron SmartShunt 4.2.3 · 2026-11-07

## Deutsch
Die Quelldateien wurden syntaktisch geprueft; die komplette Paketstruktur,
Manifest-/App-Konfiguration, Lizenzhinweise und deutsche/englische
Beschreibungen/Installationsanleitungen kontrolliert.
Es wurden keine allgemeinen Shell-Befehle, Netzwerkaufrufe, Firmwareupdates,
Home-Assistant-Restarts oder Hardware-Schreibbefehle ausgefuehrt.

**Geprueft (statische Pruefung und isolierte Offline-Testvektoren):**
- 4.2.3 AppArmor on, no SYS_RAWIO, no HA /config mount.
- HEX and raw publish disabled; /data log enforced.
- VE.Direct HEX pure codec GET/SET sample vectors passed.
- The original 4.2.2 add-on was live and delivered SmartShunt telemetry on Womo HA Core 2026.10.1; the 4.2.3 permissions have NOT been tested on actual VE.Direct hardware.
- A controlled first installation is required before replacing working 4.2.2 in a battery-critical motorhome.

- Bestaetigte automatische pruefbare Einzelpunkte: 61.
- Keine typischen privaten Schluessel-/Tokenpraefixe in diesen Pakettexten erkannt.
- Diese Pruefung ersetzt keinen isolierten Installations-/Hardwaretest auf
  fremden Geräten. Der Live-Quellstand bzw. die laufende Basisversion wurde
  gesondert am Womo-Home-Assistant kontrolliert.
- Weitere Test-Grenzen stehen im README und der Installationsanleitung.

## English
The source files passed syntax/structure checks and the package documents,
licensing, local-only defaults and selected offline vectors were reviewed.
No firmware, live Home Assistant configuration, connected battery or Bluetooth
sensor was modified by these tests.

**Check points:** 138 assertions/conditions passed in the offline
validation script. Compatibility with other hardware, configurations, serial
permissions, battery chemistries and Home Assistant versions is not guaranteed.

## Run these checks again
Run `tests/validate_and_pack_20261107.py` from the private documentation
repository when the source tree changes; keep the source archive and checksums.
The package is intended for publication **only after explicit approval**.

# QA-REPORT · Truma LevelControl BLE 0.3.0 · 2026-11-07

## Deutsch
Die Quelldateien wurden syntaktisch geprueft; die komplette Paketstruktur,
Manifest-/App-Konfiguration, Lizenzhinweise und deutsche/englische
Beschreibungen/Installationsanleitungen kontrolliert.
Es wurden keine allgemeinen Shell-Befehle, Netzwerkaufrufe, Firmwareupdates,
Home-Assistant-Restarts oder Hardware-Schreibbefehle ausgefuehrt.

**Geprueft (statische Pruefung und isolierte Offline-Testvektoren):**
- # Reference result: 9.24 kg in model, 9.20 kg in manufacturer app, delta +0.04 kg
- # WARNING: approximate geometry, verify at multiple levels against the app
- Eight installed source files were previously compared byte-for-byte with the running Womo HA Core 2026.10.1 integration; all matched.
- Womo configuration entry was loaded. Sensor battery 8% and BLE errors were observed; physical battery replacement is advisable.

- Bestaetigte automatische pruefbare Einzelpunkte: 75.
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

**Check points:** 75 assertions/conditions passed in the offline
validation script. Compatibility with other hardware, configurations, serial
permissions, battery chemistries and Home Assistant versions is not guaranteed.

## Run these checks again
Run `tests/validate_and_pack_20261107.py` from the private documentation
repository when the source tree changes; keep the source archive and checksums.
The package is intended for publication **only after explicit approval**.

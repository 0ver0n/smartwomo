# Installation – Truma LevelControl BLE 0.3.0 (Deutsch)

## Voraussetzungen
- Home Assistant mit funktionierender Bluetooth-Integration und erreichbarem Truma-LevelControl-Sensor.
- Ein Bluetooth-Adapter beziehungsweise unterstützter Bluetooth-Proxy mit GATT-Zugriff. Der ursprüngliche Stand wurde am Raspberry des Wohnmobils betrieben.
- Zugriff auf das Verzeichnis `/config/custom_components/` und Berechtigung, Home Assistant Core kontrolliert neu zu starten.

## Vorgehen
1. Vorhandenen Home-Assistant-Stand und die aktuelle Integration sichern. Falls eine frühere `truma_levelcontrol` vorhanden ist, deren Originalordner und Config Entries dokumentieren.
2. Aus dem Veröffentlichungspaket den vollständigen Ordner `custom_components/truma_levelcontrol/` mit allen Python-, JSON- und Übersetzungsdateien nach `/config/custom_components/truma_levelcontrol/` kopieren. Es muss dort direkt `manifest.json` liegen.
3. Die kopierten Dateien mit der Version 0.3.0 vergleichen. Konfigurationsdateien anderer Integrationen nicht ersetzen.
4. Home Assistant Core nach Konfigurationsprüfung kontrolliert neu starten. Keinen gesamten Raspberry-Neustart ohne Grund durchführen.
5. Unter **Einstellungen → Geräte & Dienste → Integration hinzufügen** die Integration „Truma LevelControl BLE“ auswählen. Alternativ eine erkannte Bluetooth-Gerätemeldung bestätigen.
6. Falls die automatische Erkennung ausbleibt, die Geräte-Bluetooth-Adresse im manuellen Einrichtungsdialog eingeben. Diese Adresse ist **geräteindividuell**; keine fremde Beispieladresse kopieren.
7. Sensoren für Batteriezustand, Temperatur, Füllhöhe und geschätzten Füllstand prüfen. Nach dem ersten Abfrageintervall bis zu 30 Minuten warten; bei initialem Fehler Bluetooth-Signal und Logs prüfen.

## Betrieb und Fehlerbehebung
- Es werden nur BLE-Daten gelesen, nicht die Truma-Heizung oder der Füllstandssensor gesteuert.
- Die %- und kg-Werte beziehen sich nur auf das kalibrierte **11-kg-Stahlflaschenprofil**. Anderen Profilen keine Genauigkeit zuschreiben.
- Bei `unavailable`: Reichweite, BLE-Adapter, gleichzeitig verbundene Hersteller-App, Home-Assistant-Logs und `bleak`-Verbindung prüfen. Keine wild geratenen GATT-Schreibbefehle senden.
- Bei Updates zuerst aktuellen Stand sichern; nur eine Version der Integration gleichzeitig vorhalten. Rollback durch Wiederherstellung des gesicherten Verzeichnisses und kontrollierten Core-Neustart.
- Kontakt/Fehlerberichte nach Veröffentlichung über GitHub Issues; keine MAC-Adressen, privaten Logs oder personenbezogenen Daten öffentlich posten.

## Flaschengröße wechseln / Kalibrierung

**Vor der Installation einer anderen Flasche muss das Profil angepasst werden.** Dazu die vollständige [Anleitung für Flaschenprofile](FLASCHENPROFILE.de.md) lesen. Dort stehen die **genau zu ändernden Konstanten in `const.py`**, eine ausführliche Erklärung von Wasserinhalt, Geometrie und Dichte sowie ein Beispielaufruf der mitgelieferten Offline-Rechenhilfe `tools/calibrate_bottle.py`.

Die Voreinstellung gilt ausdrücklich nur für das bisher kalibrierte 11-kg-Stahlflaschenmodell. Es gibt in Version 0.3.0 **keinen eigenständigen Dialog zum Auswählen anderer Profile**; wer mehrere verschiedene Flaschentypen gleichzeitig verwendet, braucht eine zusätzliche per-Gerät-Profillogik. Der Füllstand in Prozent und kg ist bei einem anderen Profil ohne Anpassung möglicherweise falsch.

**Prüfnachweis für Version 0.3.0:** Der Originalquellcode stimmt mit dem laufenden Womo-System Home Assistant Core 2026.10.1 überein. Eine geladene Integration und echte Sensorwerte wurden überprüft. Wiederholte Bluetooth-Verbindungsfehler können bei schwacher Sensorbatterie auftreten; dann zuerst Batterien und Signal prüfen, ohne das Produktivsystem zu verändern. Genaue Prozent-/kg-Werte für andere Flaschen sind erst nach eigener Kalibrierung belegbar.

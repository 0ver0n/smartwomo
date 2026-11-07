# Victron SmartShunt – Home-Assistant-App mit VE.Direct und MQTT

**Version:** 4.2.3 · **Projektinitiator:** Marcel Lörz (0ver0n), https://www.blindmitwomo.com · **Lizenz:** Apache-2.0.

Diese unabhängige, kostenlose Home-Assistant-App liest die Messdaten eines per VE.Direct-USB-Kabel angeschlossenen Victron SmartShunt aus und überträgt sie an einen MQTT-Broker. Home Assistant erkennt die Geräte und Sensoren über MQTT Discovery.

## Funktionen
- Messwerte für Batteriestrom, -spannung, Ladezustand, Leistung, historische Entladungen, Alarme und weitere vom Gerät gemeldete VE.Direct-Werte.
- Optionale Diagnose-/Rohdaten und zyklische zusammengefasste Messwerte.
- Stabilere Parserbehandlung bei getrennten Live- und Historien-Telegrammen, automatischer serieller Wiederverbindungsversuch und MQTT-Wiederverbindung.
- **Optional**: Lesen der SmartShunt-Register über VE.Direct HEX und Änderung ausgewählter Einstellungen über MQTT. Diese Funktion ist **standardmäßig AUS** und darf nur von Anwendern aktiviert werden, die Auswirkungen auf die Batterieüberwachung kennen.

## Sicherheit in 4.2.3
- AppArmor wieder aktiviert; keine angeforderte `SYS_RAWIO`-Linuxfähigkeit und **kein Zugriff auf die Home-Assistant-Konfiguration**.
- Der serielle Gerätezugriff läuft über `uart: true` und `udev: true`; das Gerät muss für die Home-Assistant-App erreichbar sein.
- Logdateien liegen ausschließlich im persistenten App-Verzeichnis `/data`, nicht mehr in `/config`. Ein alter, gespeicherter Logpfad außerhalb `/data` wird automatisch verworfen.
- `publish_raw=false` und `hex_enabled=false` als sichere Standardwerte.
- MQTT-Benutzername und Passwort gehören ausschließlich in die App-Optionen, **niemals in öffentliche Konfigurationsdateien**.
- Freigegebene HEX-Schreibzugriffe können unter anderem Ladezustand, Alarmschwellen und Batterieparameter verändern. Vor Aktivierung die sichere MQTT-Zugriffssteuerung prüfen.

## Voraussetzungen und Grenzen
Getestete Basis: Victron SmartShunt 300 A über VE.Direct-USB mit Home Assistant auf dem Womo. Die ursprüngliche App 4.2.2 läuft dort mit Core 2026.10.1, sendet tatsächlich Messwerte und ist als gestartet bestätigt. Version 4.2.3 minimiert Rechte und ändert sichere Defaults; sie muss in der Zielumgebung vor dem produktiven Wechsel geprüft werden. Nicht jede VE.Direct-Firmware oder jedes SmartShunt-Modell ist damit automatisch zertifiziert.

**Anleitung:** [Installation und Fehlerbehebung (Deutsch)](INSTALLATION.de.md) · [English](INSTALLATION.en.md). [Technischer Prüfbericht](QA-REPORT.md). [Änderungshistorie](CHANGELOG.md).

Unabhängiges Communityprojekt, nicht offiziell von Victron Energy. Falsche Ladezustände oder verstellte Batterieparameter können zu Schäden führen; nie ungeprüft als alleinige Sicherheitsabschaltung verwenden.

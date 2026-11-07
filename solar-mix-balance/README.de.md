# Solar Mix Balance: Solarstrom, Batterie, Netzbezug und Kosten in Home Assistant

**Entwicklung:** Marcel Lörz · https://www.blindmitwomo.com · GitHub 0ver0n. **Lizenz:** Apache-2.0. **Veröffentlichte Version:** 5.8.2 · https://github.com/0ver0n/smartwomo/tree/main/solar-mix-balance.

Solar Mix Balance ist unsere eigene, kostenlose Home-Assistant-Integration. Sie verbindet vorhandene Messentitäten für Photovoltaik, Batterie und Netzbezug zu verständlichen Energie- und Kostenstatistiken. Die Integration kann unter anderem mit Messwerten von Zendure, EcoFlow oder beliebigen passend gemessenen Verbrauchs- und Einspeisezählern arbeiten. Sie benötigt keine eigene Cloud.

## Funktionen
- Aktuelle PV-Leistung, Netzwirkleistung, Hausverbrauch, Batterieein- und -ausgang und geschätzter Autarkie-/Eigenverbrauchsanteil.
- Historische Tages-, Wochen-, Monats- und Jahreswerte sowie Vergleichswerte und Differenzen.
- Monatsarchiv und lokale Zustandswiederherstellung über Home Assistants Speicher sowie CSV/JSON-Sicherungen.
- Monatlich einstellbare Strom-Arbeitspreise und Jahreskostenberechnung aus vorhandenen Monatsarchiven.
- **Nachträglicher Monatsnetzbezug** für belegte Lücken in älteren Monatsarchiven, ohne fremde Solar- oder Batteriewerte zu erfinden.
- Einrichtungsdialog für Quellen-Entitäten, auswählbare Sensorgruppen und einmalige Startwerte.
- Erweiterte Kalibrierungsaktion zur kontrollierten Korrektur interner Energie-Akkumulatoren.

## Version und Herkunft
**Praxisprüfung am 07.11.2026:** Version **5.8.2 wurde auf dem Haus-Home-Assistant Core 2026.10.1 installiert und nach Konfigurationsprüfung kontrolliert neu gestartet**. Alle 172 zuvor vorhandenen Solar-Mix-Entitäten blieben erhalten, alle fünf Aktionen sind registriert und die frühere Parserwarnung zu `services.yaml` trat nach dem Neustart nicht erneut auf. Die Sicherung der Altversion wurde per SHA-256 geprüft, sämtliche sechs Solar-Mix-Datendateien waren nach dem Neustart vorhanden, und die gespeicherte Home-Assistant-Config-Entry-Datei ist vor und nach dem Update **bytegleich**. Die drei historischen Monatsnetzbezugseinträge sind erhalten. Berechnungswerte liefen ohne Rücksetzung weiter.

## Wichtige Grenzen
- Energieergebnisse hängen von **korrekten Einheiten und Signalrichtungen** ab. Solarleistung, Netzbezug und Hauslast müssen passend zugeordnet sein. Doppelzählungen und ein falsches Vorzeichen verfälschen Ergebnisse.
- Strompreiswerte müssen **vom Anwender selbst eingetragen** werden. Es wird kein privater Tarif und keine frühere Rechnung mitgeliefert.
- Das ursprüngliche Programm kennt einige optionale, auf frühere Installationen abgestimmte Entitätsnamen als Legacy-Migrationshilfe. Diese sind keine verpflichtenden Entitäten und müssen im eigenen System kontrolliert bzw. über die Integration angepasst werden.
- Archiv-/Backupdaten bleiben im Home-Assistant-Konfigurationsbereich und dürfen nicht mit dem öffentlichen Quellcode geteilt werden. Die Integration ist kein zertifiziertes Abrechnungssystem.
- Eine neue Installation muss sauber getestet werden, besonders Datenmigration und Zeitraumsprünge (Monats-/Jahreswechsel). Der bestehende Betrieb auf dem Haus ist **kein Nachweis, dass sämtliche Schritte der bereinigten 5.8.2 auf beliebigen Installationen funktionieren**.

**[Installation, Erstkonfiguration, Update, Wiederherstellung (Deutsch)](INSTALLATION.de.md)** · [English](INSTALLATION.en.md) · [Änderungen](CHANGELOG.md) · [Prüfbericht](QA-REPORT.md).

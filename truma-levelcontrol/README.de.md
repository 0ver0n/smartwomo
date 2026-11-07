# Truma LevelControl BLE – eigene Home-Assistant-Integration

**Version:** 0.3.0 · **Urheber und Projektinitiator:** Marcel Lörz (GitHub: 0ver0n) · https://www.blindmitwomo.com · **Lizenz:** Apache-2.0.

Mit dieser eigenen Home-Assistant-Integration kann ein Truma-LevelControl-Sensor direkt über den lokalen Bluetooth-Adapter des Home Assistants ausgelesen werden, ganz ohne Truma-Cloud oder iNet Box. Die Integration ist nicht offiziell von Truma und nicht von Truma zertifiziert.

## Funktionen

- Automatische Bluetooth-Erkennung oder manuelle Eingabe der individuellen Geräteadresse.
- Mehrere LevelControl-Sensoren können eingebunden werden. **In 0.3.0 gilt jedoch dieselbe Flaschenberechnung für alle gleichzeitig angemeldeten Geräte.**
- Batterie, Bluetooth-Signal, Temperatur, Ultraschall-Laufzeit, Flüssigkeitshöhe sowie geschätzte Gasmasse (kg) und Füllstand (%).
- Diagnosewerte, Rohdaten optional, und Plausibilitätsprüfung gegen fehlerhafte Reflexionen. Es werden **keine BLE-Schreibbefehle** ausgeführt.
- Abfrageintervall 30 Minuten; die erforderliche Zeit für den GATT-Aufbau wird berücksichtigt.

## Unbedingt vor Benutzung lesen

Der mitgelieferte Standard ist **für genau eine deutsche 11-kg-Stahl-Eigentumsflasche kalibriert** (289 mm Flüssigkeitshöhe entsprachen in der Hersteller-App 84 % bzw. 9,2 kg am 15.09.2026). Eine andere 5-, 11- oder 33-kg-Flasche kann andere Maße und Gewölbe besitzen. Ihr Füllstand wird nicht automatisch korrekt berechnet.

**[Andere Flaschen einstellen, Konstante für Konstante erklärt, mit Offline-Rechenhilfe](FLASCHENPROFILE.de.md).** Ein Wechsel der Größe in der offiziellen Truma-App verändert diese Integration nicht. Änderungen in `const.py` müssen mit mindestens zwei realen Hersteller-App-Messpunkten überprüft werden. Für gleichzeitig unterschiedliche Flaschenformen ist eine zukünftige getrennte Profilverwaltung notwendig.

Die Anzeige ist eine Orientierungshilfe, **kein Gasleck-, Druck- oder Sicherheitsüberwachungssystem**. Bei fehlender Aktualisierung zuerst Sensorbatterien, Entfernung und Bluetooth-Fehler prüfen. Die vom Hersteller genannten zwei AAA-Batterien müssen rechtzeitig ersetzt werden.

## Installation und Kompatibilität

[Ausführliche Installations- und Bedienungsanleitung (Deutsch)](INSTALLATION.de.md) · [English installation guide](INSTALLATION.en.md).

Aus dem Quellpaket ausschließlich das Verzeichnis `custom_components/truma_levelcontrol/` nach `/config/custom_components/truma_levelcontrol/` kopieren. Für die Profileinstellung bleibt das zusätzliche Hilfsprogramm unter `tools/calibrate_bottle.py` ein optionales Offline-Werkzeug auf deinem Computer.

**Live-Beleg:** Der Quellstand ist mit den acht direkt aus dem Womo Home Assistant Core 2026.10.1 gelesenen Dateien identisch; die Integration ist dort als geladen bestätigt. Gemessene BLE-Daten und Fehlersituationen wurden am 07.11.2026 gelesen. Eine automatische Unterstützung neuerer Core-Versionen oder beliebiger Flaschenprofile ist damit nicht zugesichert.

**Projekt und Lizenz:** Apache License 2.0, [Lizenztext](LICENSE) und [Herkunftshinweis](NOTICE). Nicht autorisiert oder unterstützt durch Truma. Keine Secrets oder individuelle Sensoradresse im Quellpaket.

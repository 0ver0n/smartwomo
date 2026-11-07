# Solar Mix Balance v5.8.2 – Prüfung / QA – 07.11.2026

## Deutsch
Die ursprüngliche Haus-Integration verwendete intern 5.8.1 bei
fälschlich auf 5.7.0 stehendem Manifest. Am 07.11.2026 wurde der
korrigierte Kandidat 5.8.2 nach vollständiger Sicherung tatsächlich
auf dem Haus-Home-Assistant Core 2026.10.1 installiert, kontrolliert
neu gestartet und mit dem nativen Home-Assistant-API nachgeprüft.
Alle 172 registrierten Sensor-Entitäten, alle fünf Aktionen und
alle drei manuell gespeicherten Monatsnetzbezugseinträge blieben erhalten.
Quellcode ohne alte .bak-Dateien und ohne persönliche CSV- oder
Abrechnungsdaten gesichert; alle Python- und JSON-Dateien syntaktisch
geprüft und die Service-YAML-Beschreibungen mit fünf Aktionen und
deutschen/englischen Übersetzungen abgeglichen.
Vier echte synthetische Rechenfälle des extrahierten
_year_price_costs-Originalalgorithmus geprüft:
Monatsarchiv, belegte Netzarchivlücke, Archiv-Vorrang, Rest-Fallback
und leerer Nullfall. Keine persönlichen Werte verwendet.

Das alte Systemlog meldete einen services.yaml-Parserfehler
bei Preis-Selector.step. Mit dem korrigierten Wert step: any wurden
alle fünf Aktionen nach einem echten Core-Neustart erfolgreich
registriert. Die frühere Parserwarnung trat anschließend nicht erneut auf.

DATENERHALT: Alle 6 historisch archivierten Solar-Mix-Dateien sind weiter
vorhanden (kein Pfadverlust). Die komplette Config-Entry-Speicherdatei
hatte vor und nach dem Update einen identischen SHA-256-Wert.
Die konkrete Prüfsumme und der Rückweg stehen im privaten Wartungsbericht.
Anstelle echter Messwerte bestätigt die private Abnahme:
Jahres-, Monats- und Vorjahresdaten waren vor und nach dem Update
plausibel vorhanden, und fortlaufende Zählerstände wurden nicht zurückgesetzt.
Die konkreten Messwerte, Sicherungspfade und Prüfsummen des privaten
HA-Zustands werden nicht öffentlich veröffentlicht.
Der alte Quellstand und Zustände wurden privat vorab gesichert.
Keine Restore-Aktion war notwendig.

GRENZEN: 19 unknown-Werte betreffen überwiegend nicht vorhandene
Vorjahres-Daten; ein früherer Diagnosesensor steht auf restored/unavailable,
weil die bisherige Konfiguration ausschließlich basic und compare aktiviert.
Die Gruppenauswahl und historische Einträge wurden absichtlich NICHT
geändert. Die fünf registrierten Aktionen wurden nach dem Neustart
gelesen, aber keine produktiven Strompreis-/Kalibrier-Schreibaktionen
testweise ausgeführt, um reale Daten nicht zu verändern.

## English
The original installed version had internal version 5.8.1 but manifest
5.7.0. On Nov 7, 2026, the 5.8.2 package was installed on the house HA
Core 2026.10.1. HA Core was restarted and the integration loaded.
All 172 previous sensor entities and five described actions remained.
All six historical data files still existed and the persisted HA
config-entry file retained an identical SHA-256 hash, including the
three manual historical grid-energy month entries.
The original YAML-selector parser warning did not recur.
Four isolated synthetic tests still exercise the original annual
grid-cost calculation, using no private energy data.
No real service actions that would change electricity prices, energy
archives or calibration values were invoked. Older missing-year
sensors can remain unknown; one restored diagnostic registry entity
is unavailable because only basic/compare groups are selected.
Compatibility beyond the tested HA system requires separate validation.

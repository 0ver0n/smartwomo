# Solar Mix Balance 5.8.2 installieren

## Voraussetzungen
Home Assistant mit Unterstützung eigener Integrationen (auf unserem Referenzsystem Core 2026.10.1), lokale Quellsensoren für Solar, Batterie, Hausverbrauch bzw. Netzbezug und Zugriff auf `/config/custom_components/`. Die verwendeten Sensoren können aus Zendure-, EcoFlow- oder anderen Integrationen stammen. Keine Internetverbindung zu einem Solar-Mix-Dienst erforderlich.

## Neue Installation
1. Eine aktuelle Home-Assistant-Sicherung anlegen. Ein bereits existierender `solar_mix_balance`-Ordner darf nicht ohne Sicherung überschrieben werden.
2. Den **vollständigen** Ordner `custom_components/solar_mix_balance/` aus dem Paket nach `/config/custom_components/solar_mix_balance/` kopieren; `manifest.json`, Python-Dateien, `services.yaml`, `strings.json` und `translations/` müssen vollständig vorhanden sein. **Keine** älteren `.bak`-Dateien, private Backup-JSON oder Stromrechnungen importieren.
3. Home-Assistant-Konfiguration prüfen und Home Assistant Core anschließend kontrolliert neu starten.
4. Unter **Einstellungen → Geräte & Dienste → Integration hinzufügen** nach **Solar Mix Balance** suchen. Im Einrichtungsdialog die vorhandenen Messentitäten zuordnen. Für jede Quelle die richtige physikalische Größe prüfen: W, kWh, Laden vs. Entladen, Netzbezug vs. Einspeisung. Leere oder nicht verfügbare Felder als „Nicht konfigurieren“ belassen.
5. Nach dem Einrichten zunächst einen hellen und einen dunklen Zeitraum kontrollieren: PV-Leistung, Netzbezug, Hausverbrauch, Batteriefluss und Vorzeichen mit den eigentlichen Geräten vergleichen.
6. Die gewünschten Sensorgruppen aktivieren. Periodenwerte (Tag, Woche, Monat, Jahr) nur mit plausiblen Anfangsständen befüllen. Die Integration erzeugt Archiv-/Zustandsdateien lokal in der eigenen HA-Konfiguration.
7. In den **Entwicklerwerkzeugen → Aktionen** bei Bedarf `solar_mix_balance.set_month_price` zum Hinterlegen des monatlichen Strom-Arbeitspreises verwenden. `month` ist 1–12, `price` der Preis in **EUR/kWh**, `year` optional.
8. Bei belegten Lücken in einem **älteren** Monatsarchiv `solar_mix_balance.set_month_grid_energy` mit `month`, `kwh` und optional `year` verwenden. Der ergänzte Monat ändert ausschließlich das getrennte Monatsnetzbezugsarchiv, nicht die historischen Solar-/Batteriewerte.
9. `clear_month_price` und `clear_month_grid_energy` entfernen ausschließlich die jeweilige manuelle Ergänzung. **`calibrate_period` verändert interne Akkumulatoren und sollte nur nach Sicherung und nachvollziehbarer Messung ausgeführt werden.**

## Upgrade von einer älteren Version
Vorher den gesamten Integrationsordner, HA-Konfigurationseintrag sowie die **privaten** Datenverzeichnisse und HA-Storage-Dateien sichern. Bei der Entwicklung lagen die periodischen CSV-Daten in `/config/solar_mix_balance_data/`; das ist **kein** öffentlicher Quellcode. Die bereits bekannten Sensor-Entity-IDs nach dem Neustart auf Kontinuität und plausible historische Werte überprüfen. Bei bestehenden Installationen mit älteren Migrationen ausdrücklich einen Test-Clone verwenden. Die Version **5.8.2 wurde am 07.11.2026 auf dem Haus-System erfolgreich installiert und getestet**: Home Assistant Core 2026.10.1 startete wieder, die Integration steht auf `loaded`, alle 172 bekannten Sensoren und fünf Aktionen blieben verfügbar, drei historische Monatsdaten-Einträge erhalten. Der alte Quellcode und alle Solar-Mix-Datendateien wurden zuvor separat gesichert.

## Fehlerbehebung und Rückweg
- Wenn Werte `unknown` sind: Entität existiert? Liefert sie numerische W/kWh-Werte? Stimmen die Einheit und das Vorzeichen?
- Wenn Solar- oder Hausenergie doppelt zählt: Überschneidende Sensoren/Zähler und gleichzeitige kumulierte Energiequellen prüfen.
- Wenn historische Stromkosten nicht stimmen: Monatsarchiv, ausdrücklich gesetzte Monatswerte und Preis pro kWh kontrollieren.
- Wenn der Aktionsdialog fehlt: Core-Log nach `services.yaml`-Parserwarnungen durchsuchen; in der neuen Version sind alle fünf Aktionen beschrieben und übersetzt.
- Bei Fehlern die vorher gesicherte Integration und Konfigurationsdaten **vollständig** wiederherstellen und Core kontrolliert neu starten. Keine gesamten HA-Datenbanken ersetzen, sofern nicht unabhängig notwendig.

**Datenschutz:** Kein reales Zählerarchiv, keine privaten Entitätslisten, Rechnungen, Kundendaten oder Preisverträge sind Bestandteil dieses Pakets. Personenbezogene Daten und Live-Statistiken gehören nicht in GitHub-Issues.

**Hinweis:** Die Angaben sind technische Orientierungswerte, keine geeichte Energieabrechnung.

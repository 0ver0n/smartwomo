# Victron SmartShunt 4.2.3 – Installation, Betrieb und Rückweg

## Voraussetzungen
- Home Assistant OS oder Supervised mit lokalen Apps/Add-ons; geeigneter USB-VE.Direct-Adapter am Host.
- Funktionierender MQTT-Broker, zum Beispiel Mosquitto, mit eigenen Zugangsdaten.
- Ein SmartShunt mit aktiviertem VE.Direct-TEXT-Protokoll; die Entwicklung wurde mit SmartShunt 300 A getestet.
- Vor Änderungen eine aktuelle Home-Assistant-Sicherung und das bisherige Add-on einschließlich seiner gespeicherten Optionen bereithalten.

## Installation
1. Das Paket entpacken. Den **gesamten Unterordner `addon/`** mit `config.yaml`, `Dockerfile`, `run.sh` und `shunt.py` in ein passendes Unterverzeichnis des **lokalen Home-Assistant-App-Repositories** kopieren. Der Host muss diese lokalen Apps unterstützen.
2. Den lokalen App-Store neu laden. Die App `Victron SmartShunt` mit Versionsnummer **4.2.3** auswählen. Vorher prüfen, dass nicht eine andere aktive Instanz bereits denselben VE.Direct-USB-Port verwendet. **Nie zwei Programme gleichzeitig auf denselben seriellen Port zugreifen lassen.**
3. Den seriellen Adapterpfad unter Home Assistant **Einstellungen → System → Hardware** prüfen. In den App-Optionen `serial_device` auf den tatsächlichen Pfad setzen. Wenn vorhanden, ist ein stabiler Pfad unter `/dev/serial/by-id/` oft besser als ein wechselndes `/dev/ttyUSB0`.
4. MQTT-Host (bei Mosquitto häufig `core-mosquitto`), Port und selbst gewählte Zugangsdaten konfigurieren. Keine echten Passwörter in README, Screenshots, GitHub-Issues oder `config.yaml` eintragen.
5. Für einen ersten sicheren Test `hex_enabled=false` und `publish_raw=false` lassen. `log_file` sollte innerhalb `/data/` liegen. Danach die App installieren/starten.
6. Logs auf MQTT-Verbindung und VE.Direct-Daten prüfen. In Home Assistant die neuen MQTT-Discovery-Sensoren für **SOC, Batteriespannung, Strom, Leistung und Alarmstatus** kontrollieren. Messwerte mit der Victron-App oder einem unabhängig bekannten Referenzwert plausibilisieren; Aktualität der Messungen kontrollieren, nicht nur einen gespeicherten Zustand.
7. Falls nach einer Umstellung aus einer alten Version noch HEX-Schreib-Entitäten sichtbar sind, obwohl HEX ausgeschaltet ist: Das können **verbleibende MQTT-Retained-Discovery-Einträge** aus der früheren Version sein. Sie dürfen nicht als aktive Schreibfunktion angesehen werden. Diese Einträge bei Bedarf gezielt im MQTT-Broker entfernen, ohne unbeteiligte Geräte oder deren Discovery-Daten zu löschen.

## VE.Direct HEX bewusst aktivieren
`hex_enabled=true` erlaubt zusätzliche Registerabfragen und aktiviert bei unterstützter Hardware auch ausgewählte **MQTT-Schreibbefehle**. Zuerst sicherstellen, dass nur vertrauenswürdige Clients auf die Befehlstopics `victron/shunt/command/#` veröffentlichen können. Vor der Aktivierung die aktuelle Shunt-Konfiguration sichern und nach jedem geänderten Parameter das Ergebnis gegenprüfen. Die Batterieüberwachung muss unabhängig von dieser Erweiterung abgesichert sein. Für reine SOC-/Spannungsanzeigen bleibt HEX AUS.

## Fehlerbehebung
- **Serielles Gerät nicht erreichbar:** USB-Verbindung, passender Gerätepfad, AppArmor, UART-Freigabe und Zugriffsrechte prüfen. 4.2.3 entfernt die frühere breite `SYS_RAWIO`-Freigabe. Nicht blind `apparmor: false` eintragen.
- **MQTT nicht verbunden:** Broker-Hostname, Passwort, Berechtigungen und Protokoll prüfen. Verbindungsausfälle können die Daten veralten lassen.
- **Messwerte alt:** `last_reported` betrachten. Historische Werte und Livewerte können in getrennten VE.Direct-Rahmen übertragen werden.
- **HEX-Timeout:** HEX deaktivieren, TEXT-Werte prüfen und den USB-Rückkanal untersuchen, bevor irgendein Schreibversuch erfolgt.
- **Logging:** Dateien werden in `/data` aufbewahrt. Eine alte Logpfadoption `/config/log/...` wird aus Sicherheitsgründen ignoriert; Logs bleiben im App-Datenvolumen.
- **Updates:** Vorher Code, Optionen und den bekannten guten Stand sichern; danach alle Sensoren und die Start-/Stoppfunktion kontrollieren.

## Wiederherstellung
Die frühere **produktive Womo-Version 4.2.2** niemals ohne Rückweg überschreiben. Im Fehlerfall neue App stoppen, die gesicherte alte Quellversion und ihre Optionen wiederherstellen, nur die betroffene App kontrolliert neu starten und Telemetrie sowie MQTT-Discovery kontrollieren. Keine globale Home-Assistant-Konfiguration, Datenbank oder Sicherheitsautomationen aus einem bloßen Test heraus verändern.

**Sicherheit:** Projekt ist keine alleinige Lade- oder Batterieschutzfunktion. Keine Herstellergarantie oder Unterstützung durch Victron Energy.

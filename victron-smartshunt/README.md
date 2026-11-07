# Victron SmartShunt VE.Direct → MQTT → Home Assistant

**[Deutsch](README.de.md) · [English](README.en.md)**

Independent, open-source Home Assistant local add-on for reading a Victron SmartShunt over a USB VE.Direct cable and publishing sensor values via MQTT Discovery.

**Project initiator:** Marcel Lörz ([0ver0n](https://github.com/0ver0n)) · https://www.blindmitwomo.com

**Release version:** 4.2.3 · **License:** [Apache-2.0](LICENSE) · [Origin notice](NOTICE)

**Security defaults:** AppArmor enabled; no `SYS_RAWIO`; no mount of Home Assistant's configuration directory; persistent logs only in the add-on's `/data`; raw MQTT publishing OFF; optional VE.Direct HEX reading and writing OFF by default. HEX setting commands must be deliberately enabled.

[Installationsanleitung Deutsch](INSTALLATION.de.md) · [English installation guide](INSTALLATION.en.md)

**Compatibility:** Source basis v4.2.2 is running on the author's motorhome Home Assistant Core 2026.10.1. The security-hardened 4.2.3 configuration is separately prepared and tested as documented in [QA-REPORT.md](QA-REPORT.md). It is not an official Victron Energy product. Read the safety notes before changing battery-monitor settings.

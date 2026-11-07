# Solar Mix Balance: solar power, batteries, grid import and energy costs for Home Assistant

**Original development:** Marcel Lörz · https://www.blindmitwomo.com · GitHub 0ver0n. **License:** Apache-2.0. **Open-source release:** 5.8.2 · https://github.com/0ver0n/smartwomo/tree/main/solar-mix-balance.

Solar Mix Balance is an independent, free Home Assistant integration. It combines existing PV, battery and grid meter entities into calculated energy and cost statistics. It can work with sources such as Zendure, EcoFlow and suitable other meters; no separate cloud service is required.

## Features
- Live PV and grid power, home consumption, battery charge/discharge, and estimated self-consumption and self-sufficiency.
- Daily, weekly, monthly, and yearly historical statistics with comparisons.
- Local archiving and recovery through Home Assistant storage and CSV/JSON backups.
- Individually configurable electricity prices by month, including annual grid-cost calculations.
- **Verified historical monthly grid imports** for gaps in older monthly records, without inventing PV/battery figures.
- UI-based entity mapping, configurable sensor groups, and optional starting totals.
- Advanced recalibration action for energy accumulators and related meter snapshots.

## Version and provenance
**Live test on November 7, 2026:** Version **5.8.2 was installed on the author's Home Assistant Core 2026.10.1 and the core restarted after a configuration check**. All 172 original Solar Mix entities remained, all five actions are registered, and the previous `services.yaml` parsing warning did not recur. The original code and related data were backed up with a verified SHA-256 hash. All six private Solar Mix data files remained present, and the stored config-entry file was byte-identical before and after the upgrade. Three manually entered monthly grid figures survived; annual readings continued rather than resetting.

## Limitations
- Calculations require correctly mapped sensors with appropriate units and import/export signs. Double-counting or reversing a meter's sign leads to incorrect totals.
- **No electricity tariffs, invoices, private meter histories or customer records are distributed.** Enter your own prices and validate them.
- Some optional migration helpers still recognize legacy example entity names. They are not required for a new installation; review each selection in your own system.
- Persistent data lives locally inside Home Assistant. Never publish your live CSV files, configuration entries, backups or database.
- This is not certified accounting software. Migrating from existing installations and calendar boundaries should be tested with complete backups.
- A live v5.8.1 installation does not prove that the cleaned v5.8.2 candidate works unchanged on every setup.

**[English installation, initial setup, upgrades and rollback](INSTALLATION.en.md)** · [Deutsch](INSTALLATION.de.md) · [Changelog](CHANGELOG.md) · [QA report](QA-REPORT.md).

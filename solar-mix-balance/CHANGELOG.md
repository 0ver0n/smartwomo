# Changes / Änderungen

## 5.8.2 (open-source release, 2026-11-07)
- Extracted complete **currently installed** integration sources from the house Home Assistant. No historic backup files, HA database, private CSV archives or user-specific billing data included in this candidate.
- Fixed version mismatch: installed `manifest.json` still declared 5.7.0 while active `const.VERSION` was 5.8.1. Candidate now consistently declares **5.8.2**.
- Replaced obsolete `home-assistant-solar-mix-balance/solar_mix_balance` metadata URLs with the **already existing** `0ver0n/smartwomo` repository root and its Issues page. A dedicated Solar Mix subdirectory link will only be used after actual publication.
- Added missing `services.yaml` descriptions for `set_month_grid_energy`, `clear_month_grid_energy`, and `calibrate_period` to match the five existing registered actions. Fractional number inputs use Home Assistant's `step: any` form.
- Added German/English action text under `strings.json` and `translations/de.json`, `translations/en.json`.
- Generalized two author-specific source-code comments. No broad rework of the live calculations, archived energy data, Bluetooth, batteries or home energy automations.
- Added bilingual README and installation/rollback instructions, LICENSE/NOTICE, privacy warnings, synthetic test data and QA report.

## Post-installation validation, November 7, 2026
- Upgraded the existing house integration to 5.8.2 without recreating its config entry. Home Assistant Core 2026.10.1 restarted and the integration loaded.
- All 15 installed source files matched the reviewed candidate; 172 registered sensor entities and all five Home Assistant actions remained accessible.
- Six historical data files survived with no missing paths. The stored config-entry database had the same SHA-256 before and after the update, including three manual monthly grid records.
- Prior year grid import 4,354 kWh remained intact; current-year and monthly values continued upward normally. The former services.yaml selector parser warning did not recur after startup.
- `unknown` values for unavailable historical inputs and one previously restored diagnostic registry entity remain, by design of the pre-existing `basic` + `compare` sensor group selection.
- The installed system keeps the verified private pre-upgrade archive and SHA-256 in its protected backup directory; no personal energy history is bundled with the public candidate.

## Previous running code
- `const.VERSION` 5.8.1 with manual historical grid-energy archive augmentation.
- Integrated meter mapping, PV and battery analytics, period CSVs, HA state storage and service actions.
- Actual house Home Assistant Core 2026.10.1 reported the integration `loaded`; there were live energy and cost entities.

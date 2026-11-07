# Installing Solar Mix Balance 5.8.2

## Prerequisites
Home Assistant supporting custom integrations (reference environment Core 2026.10.1), suitable local PV/battery/house/grid meter entities, and access to `/config/custom_components/`. Inputs may come from Zendure, EcoFlow or other providers. No separate Solar Mix cloud service is needed.

## Fresh installation
1. Make a current Home Assistant backup. Do not replace an existing `solar_mix_balance` directory without saving its original code and data.
2. Copy the **entire** `custom_components/solar_mix_balance/` folder from this package to `/config/custom_components/solar_mix_balance/`. Include `manifest.json`, all Python files, `services.yaml`, `strings.json`, and `translations/`. **Never** publish or copy personal archived readings or old backups into the public release tree.
3. Validate Home Assistant and restart only Home Assistant Core in a controlled manner.
4. Open **Settings → Devices & services → Add integration**, search for **Solar Mix Balance**, then map the local measurement entities. Pay attention to W vs kWh, battery charge vs discharge, and grid import vs export signs. Leave fields unused when no suitable entity exists.
5. Compare the initial PV, household, battery and grid readings to the original devices during both solar production and low-generation periods to detect sign errors or double-counting.
6. Select sensor groups and use only verified starting values if historical periods are being initialized. Period statistics, backups and Home Assistant storage stay **local**.
7. Use **Developer tools → Actions → `solar_mix_balance.set_month_price`** to assign a monthly electricity work price. Specify `month` (1–12), `price` in **EUR/kWh**, and optional `year`.
8. To fill an older monthly grid-archive gap, run **`solar_mix_balance.set_month_grid_energy`** with `month`, `kwh` and optional `year`. This does **not** fabricate historic PV or battery energy readings.
9. `clear_month_price` and `clear_month_grid_energy` only remove the corresponding manual entry. **`calibrate_period` changes internal accumulators and must only be used with a backup and valid reference reading.**

## Upgrading
Back up the existing custom integration, config entry, private data directory and relevant HA storage first. The original installation has persisted period CSVs beneath `/config/solar_mix_balance_data/`; these files are **private data**, not project source. Verify every historical sensor and entity ID after migration. For complex existing setups use a test clone first. **Version 5.8.2 was successfully installed and tested on the author's home system on November 7, 2026**, with HA Core 2026.10.1 running again, integration `loaded`, all 172 existing sensor entities and five actions preserved, and all three historical monthly grid entries intact. Original source and all Solar Mix data files were backed up first.

## Troubleshooting and rollback
- `unknown` sensors: verify the selected entity exists and delivers numeric values with the expected unit.
- Wrong energy totals: check overlapping PV meters, multiple cumulative sensors and import/export signs.
- Unexpected electricity costs: check monthly prices and which archive periods have actual readings versus manually added grid-only values.
- Missing action editor: review Home Assistant logs for `services.yaml` parsing warnings. Version 5.8.2 describes all five registered actions.
- To roll back, restore the saved integration source, config entry and private state data before restarting Core. Avoid broad database manipulation.

**Privacy:** No actual utility contracts, tariff records, electricity bills, private entity lists or stored consumption archives are distributed. Do not paste private measurements or identifiers into public bug reports.

**Disclaimer:** Estimates are not calibrated billing measurements.

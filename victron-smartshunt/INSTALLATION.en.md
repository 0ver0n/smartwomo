# Victron SmartShunt 4.2.3 – Installation, operation and rollback

## Requirements
- Home Assistant OS or Supervised with support for local apps/add-ons, a compatible USB VE.Direct adapter connected to the host.
- MQTT broker such as Mosquitto and credentials belonging to the installer.
- SmartShunt supporting VE.Direct TEXT; development and field use have been with the 300 A model.
- A current Home Assistant backup and saved original add-on files/options before performing any changes.

## Installation
1. Extract the package. Copy the **entire `addon/` folder** containing `config.yaml`, `Dockerfile`, `run.sh`, and `shunt.py` to an appropriate subdirectory of your **local Home Assistant app repository**.
2. Reload the local app store and choose `Victron SmartShunt` version **4.2.3**. Ensure there is no other running process using the same VE.Direct USB serial port. **Never open one serial port from two competing programs.**
3. Determine the correct serial adapter path under **Settings → System → Hardware**. Enter it under the `serial_device` option. A stable `/dev/serial/by-id/` device path is often preferable to a changing `/dev/ttyUSB0`.
4. Configure MQTT host (often `core-mosquitto`), port, and your own credentials in the app options. Never add real passwords to `config.yaml`, GitHub issues, documentation or screenshots.
5. Leave `hex_enabled=false` and `publish_raw=false` for the initial read-only test. Keep `log_file` inside `/data/`. Install/start the app.
6. Check logs for MQTT connectivity and VE.Direct data. Verify that MQTT Discovery creates fresh SOC, battery voltage, current, power and alarm readings. Cross-check values against Victron software or another trusted reading; examine their age, not merely whether a historical value is present.
7. If migrating from an old installation, some HEX control entities may remain visible even after HEX is disabled because their **retained MQTT discovery messages** persist. They are not evidence of active command handling. Remove only the stale retained entries belonging to this device when needed.

## Deliberately enabling VE.Direct HEX
Setting `hex_enabled=true` permits HEX register reads and, on suitable hardware, also selected **MQTT setting writes**. Secure `victron/shunt/command/#` so untrusted MQTT clients cannot publish commands. Back up the SmartShunt settings before activation and verify each deliberate change. Never rely solely on this software for battery safety. Leave HEX off for normal voltage/SOC monitoring.

## Troubleshooting
- **Serial device not accessible:** Check USB path, AppArmor, UART access and device permissions. v4.2.3 removes the previous broad `SYS_RAWIO` capability; do not blindly disable AppArmor.
- **MQTT offline:** Verify broker credentials, hostname and permissions.
- **Stale readings:** Compare timestamps; history and live data can arrive in separate VE.Direct frames.
- **HEX timeout:** Switch HEX off and check the transmit side of the USB cable before attempting writes.
- **Logging:** Persistent logs reside in `/data`; old `/config/log/` paths are deliberately ignored.
- **Upgrades:** Keep copies of code, options and working versions. Retest startup, shutdown, sensors and availability afterwards.

## Rollback
The proven motorhome v4.2.2 must not be overwritten without a recovery copy. If the new app misbehaves, stop it, restore the previously saved app directory and options, restart only the affected app, then verify MQTT Discovery and live telemetry. Do not replace the whole Home Assistant database or disable battery protection to run a test.

**Safety:** This software is not the sole battery protection or charge-control system. It is independent of and not endorsed by Victron Energy.

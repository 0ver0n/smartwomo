# Changes / Änderungen

## 4.2.3 – 2026-11-07
- Existing 4.2.2 VE.Direct TEXT parser, MQTT Discovery logic, HEX register codec and reconnect handling retained.
- **AppArmor enabled**, removed `SYS_RAWIO` capability and writable Home Assistant `/config` mapping; still provides serial access through UART/UDEV.
- Rotating file logs moved to the app's private persistent `/data` directory. Existing `log_file` values outside `/data` are replaced by the safe path.
- `hex_enabled` and `publish_raw` now **disabled by default**, both in Supervisor options and Python defaults; HEX incoming MQTT messages are explicitly ignored while disabled.
- Python dependencies pinned to pyserial 3.5 and paho-mqtt 2.1.0 for more reproducible builds.
- German/English documentation, migration guidance, safety warnings and QA report included.
- **No automatic settings migration is performed.** Existing users' saved options can override the new defaults: review them before upgrading.

## 4.2.2 – original motorhome baseline
- Existing full VE.Direct and optional HEX reading/writing, logging and reconnection functions.
- Broader privileges (AppArmor disabled, `SYS_RAWIO`, writable `/config`) and HEX enabled by default.
- The original source is preserved in the private `Projekte/Womo-SmartShunt/source/` backup.

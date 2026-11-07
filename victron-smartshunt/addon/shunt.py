#!/usr/bin/env python3
"""
Victron SmartShunt USB -> Home Assistant via MQTT (Discovery)
v4.2.3 (VE.Direct HEX: Einstellungen lesen und sicher über MQTT/HA schreiben)

Why v4.0.3 broke:
- It removed MQTT username/password support and any error handling/logging.
- If your broker requires auth (common with Mosquitto add-on), the script exits immediately,
  leaving all entities "Nicht verfügbar".

v4.1.2 restores robustness and fixes the serial frame boundary bug:
- German names
- 2 decimals for V/A/W/Ah/kWh/% (where applicable)
- Extrasensors: Ah-based values -> kWh estimated using CURRENT voltage
- raw + summary topics for verification
- console + rotating file logging
"""

import json
import logging
import os
import queue
import signal
import struct
import sys
import time
from logging.handlers import RotatingFileHandler
from typing import Any, Dict, Optional, Tuple

import serial
import paho.mqtt.client as mqtt

OPTIONS_PATH = "/data/options.json"

DEFAULT_CONFIG: Dict[str, Any] = {
    # Serial
    "serial_device": "/dev/ttyUSB0",
    "baudrate": 19200,
    "serial_timeout_s": 1,

    # MQTT
    "mqtt_host": "core-mosquitto",
    "mqtt_port": 1883,
    "mqtt_username": "",
    "mqtt_password": "",

    # Topics
    "discovery_prefix": "homeassistant",
    "state_topic": "victron/shunt/state",
    "availability_topic": "victron/shunt/status",
    "raw_topic": "victron/shunt/raw",
    "summary_topic": "victron/shunt/summary",
    "settings_topic": "victron/shunt/settings",
    "command_base_topic": "victron/shunt/command",

    # Debug publishing
    "publish_raw": False,
    "publish_summary": True,
    "summary_interval_s": 60,

    # VE.Direct HEX settings/control
    "hex_enabled": False,
    "hex_refresh_s": 3600,
    "hex_command_timeout_s": 2.5,

    # Logging
    "log_level": "INFO",
    "log_file": "/data/victron_smartshunt.log",
    "log_max_bytes": 2_000_000,
    "log_backup_count": 5,

    # Robustness
    "no_data_wakeup_s": 5,
    "reconnect_wait_s": 2,

    # Device identity
    "device_id": "victron_smartshunt_usb",
    "device_name": "Victron SmartShunt",
    "sw_version": "4.2.3",

    # Status calc
    "status_threshold_a": 0.1,

    # Sanity check (logs only)
    "log_power_sanity_check": True,
}

def load_config() -> Dict[str, Any]:
    cfg = dict(DEFAULT_CONFIG)
    if os.path.exists(OPTIONS_PATH):
        try:
            with open(OPTIONS_PATH, "r", encoding="utf-8") as f:
                user_cfg = json.load(f) or {}
            if isinstance(user_cfg, dict):
                cfg.update(user_cfg)
        except Exception:
            pass
    return cfg

config = load_config()

def setup_logging() -> logging.Logger:
    level = getattr(logging, str(config.get("log_level", "INFO")).upper(), logging.INFO)
    logger = logging.getLogger("VictronSmartShunt")
    logger.setLevel(level)
    logger.propagate = False

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")

    ch = logging.StreamHandler()
    ch.setLevel(level)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    log_file = str(config.get("log_file", "/data/victron_smartshunt.log"))
    # Public distribution: do not accept logging outside the private app data volume.
    # In particular, upgraded users may still have the old /config/log path saved.
    allowed_root = os.path.realpath("/data") + os.sep
    if not os.path.realpath(log_file).startswith(allowed_root):
        logger.warning("Logpfad ausserhalb /data abgewiesen; verwende /data.")
        log_file = "/data/victron_smartshunt.log"
    try:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        fh = RotatingFileHandler(
            log_file,
            maxBytes=int(config.get("log_max_bytes", 2_000_000)),
            backupCount=int(config.get("log_backup_count", 5)),
            encoding="utf-8",
        )
        fh.setLevel(level)
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    except Exception as e:
        logger.warning(f"File-Logging konnte nicht gestartet werden ({log_file}): {e}")

    return logger

logger = setup_logging()

RUNNING = True
HEX_COMMAND_QUEUE = queue.Queue()
HEX_SETTINGS_STATE: Dict[str, Any] = {}


def handle_shutdown(signum, _frame) -> None:
    global RUNNING
    RUNNING = False
    try:
        logger.info("Shutdown-Signal %s empfangen. Beende sauber ...", signum)
    except Exception:
        pass
    try:
        mqtt_publish(config["availability_topic"], "offline", retain=True)
    except Exception:
        pass

signal.signal(signal.SIGTERM, handle_shutdown)
signal.signal(signal.SIGINT, handle_shutdown)

def create_mqtt_client() -> mqtt.Client:
    """Create a paho client that works with paho-mqtt 1.x and 2.x without callback warnings."""
    try:
        # paho-mqtt >= 2.x
        return mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2)
    except Exception:
        # paho-mqtt 1.x fallback
        return mqtt.Client()

client = create_mqtt_client()

def normalize_reason_code(reason_code: Any) -> Any:
    try:
        return int(reason_code)
    except Exception:
        value = getattr(reason_code, "value", None)
        if value is not None:
            return value
        text = str(reason_code).lower()
        if text in ("success", "normal disconnection", "no error"):
            return 0
        return reason_code

def safe_line_display(line_bytes: bytes) -> str:
    return line_bytes.rstrip(b"\r\n").decode("ascii", errors="backslashreplace")

def parse_vedirect_line(line_bytes: bytes) -> Optional[Tuple[str, str]]:
    """
    Parse one VE.Direct text line safely.

    Important: The Checksum line contains a binary byte after the tab.
    Decoding with errors='ignore' and then strip() can remove that byte and the tab,
    so the old parser skipped Checksum and never published a complete frame.
    """
    raw = line_bytes.rstrip(b"\r\n")
    if not raw:
        return None

    # VE.Direct frame boundary. Accept it even if the binary checksum byte is non-printable.
    if raw == b"Checksum" or raw.startswith(b"Checksum\t"):
        return "Checksum", ""

    if b"\t" not in raw:
        return None

    key_b, value_b = raw.split(b"\t", 1)
    key = key_b.decode("ascii", errors="ignore").strip()
    value = value_b.decode("ascii", errors="ignore").strip()
    if not key:
        return None
    return key, value

def mqtt_publish(topic: str, payload: Any, retain: bool = False, qos: int = 0) -> None:
    try:
        if isinstance(payload, (dict, list)):
            data = json.dumps(payload, ensure_ascii=False)
        else:
            data = str(payload)
        client.publish(topic, data, qos=qos, retain=retain)
    except Exception as e:
        logger.warning(f"MQTT publish fehlgeschlagen ({topic}): {e}")

def on_connect(_client, _userdata, _flags, reason_code, *extra):
    rc = normalize_reason_code(reason_code)
    if rc == 0:
        logger.info("MQTT verbunden.")
        # Availability represents usable VE.Direct data, not only broker connectivity.
        # It is set to online after the first complete frame.
        mqtt_publish(config["availability_topic"], "offline", retain=True)
        if bool(config.get("hex_enabled", False)):
            base = str(config.get("command_base_topic", "victron/shunt/command")).rstrip("/")
            _client.subscribe(base + "/#")
            logger.info("HEX-Steuerung hört auf %s/#", base)
    elif rc == 4:
        logger.error("MQTT Auth-Fehler (Bad Username/Password).")
    elif rc == 5:
        logger.error("MQTT Nicht autorisiert.")
    else:
        logger.error(f"MQTT Connect Fehler rc={rc}")

def on_disconnect(_client, _userdata, *args):
    # paho 1.x: args=(rc,), paho 2.x: args=(disconnect_flags, reason_code, properties)
    reason = args[0] if len(args) == 1 else (args[1] if len(args) >= 2 else 0)
    rc = normalize_reason_code(reason)
    if rc != 0:
        logger.warning(f"MQTT Verbindung getrennt (unerwartet, rc={rc}). Reconnect läuft...")


def on_message(_client, _userdata, msg):
    """MQTT callback: never touch serial here; queue commands for the serial thread."""
    if not bool(config.get("hex_enabled", False)):
        return
    try:
        base = str(config.get("command_base_topic", "victron/shunt/command")).rstrip("/") + "/"
        topic = str(msg.topic)
        if not topic.startswith(base):
            return
        rel = topic[len(base):]
        payload = msg.payload.decode("utf-8", errors="replace").strip()
        if rel.startswith("set/"):
            HEX_COMMAND_QUEUE.put({"op": "set", "key": rel[4:], "value": payload})
        elif rel.startswith("action/"):
            HEX_COMMAND_QUEUE.put({"op": "action", "key": rel[7:]})
    except Exception as e:
        logger.warning("HEX MQTT Kommando konnte nicht eingereiht werden: %s", e)


client.on_connect = on_connect
client.on_disconnect = on_disconnect
client.on_message = on_message

if config.get("mqtt_username"):
    client.username_pw_set(config["mqtt_username"], config.get("mqtt_password", ""))

client.will_set(config["availability_topic"], payload="offline", qos=0, retain=True)

def connect_mqtt() -> None:
    while RUNNING:
        try:
            logger.info(f"Verbinde MQTT: {config['mqtt_host']}:{config['mqtt_port']} ...")
            client.connect(config["mqtt_host"], int(config["mqtt_port"]), 60)
            client.loop_start()
            time.sleep(1.0)
            # online is published by on_connect if connect succeeded
            return
        except Exception as e:
            logger.error(f"MQTT Verbindung fehlgeschlagen: {e} (Retry in 5s)")
            sleep_s = 5
            end_ts = time.time() + sleep_s
            while RUNNING and time.time() < end_ts:
                time.sleep(0.2)

MappingEntry = Tuple[str, Optional[float], str]  # field, factor, type

MAPPING: Dict[str, MappingEntry] = {
    # Live
    "V": ("voltage", 0.001, "float"),          # mV -> V
    "VS": ("starter_voltage", 0.001, "float"), # mV -> V
    "VM": ("midpoint_voltage", 0.001, "float"), # mV -> V (AUX=MID)
    "DM": ("midpoint_deviation", 0.1, "float"), # per mille -> % (AUX=MID)
    "T": ("battery_temperature", 1.0, "float"), # °C (AUX=TEMP)
    "I": ("current", 0.001, "float"),          # mA -> A
    "P": ("power", 1.0, "float"),              # W (float, we format to 2 decimals)
    "SOC": ("soc", 0.1, "float"),              # 0.1%
    "CE": ("consumed", 0.001, "float"),        # mAh -> Ah
    "TTG": ("ttg", 1.0, "int"),                # minutes, -1 => None

    # Alarms / status
    "Alarm": ("alarm", None, "str"),
    "AR": ("alarm_reason", None, "int"),

    # Device info
    "FW": ("fw_version", None, "str"),
    "FWE": ("fw_version_extended", None, "str"),
    "BMV": ("model_name", None, "str"),
    "PID": ("product_id", None, "str"),
    "SER#": ("serial", None, "str"),

    # Meta
    "MON": ("monitor_mode", None, "int"),

    # History
    "H1": ("hist_deepest_discharge", 0.001, "float"),
    "H2": ("hist_last_discharge", 0.001, "float"),
    "H3": ("hist_avg_discharge", 0.001, "float"),
    "H4": ("hist_cycles", 1.0, "int"),
    "H5": ("hist_full_discharges", 1.0, "int"),
    "H6": ("hist_total_drawn", 0.001, "float"),
    "H7": ("hist_min_voltage", 0.001, "float"),
    "H8": ("hist_max_voltage", 0.001, "float"),
    "H9": ("hist_time_since_full", 1.0, "int"),
    "H10": ("hist_sync_count", 1.0, "int"),
    "H11": ("hist_low_voltage_alarms", 1.0, "int"),
    "H12": ("hist_high_voltage_alarms", 1.0, "int"),
    "H15": ("hist_min_aux_voltage", 0.001, "float"),
    "H16": ("hist_max_aux_voltage", 0.001, "float"),
    "H17": ("hist_discharged_energy", 0.01, "float"),
    "H18": ("hist_charged_energy", 0.01, "float"),
}

# VE.Direct HEX register definitions (Victron BMV/SmartShunt HEX protocol).
# scale converts raw register units -> user units. All register IDs/types below
# are documented by Victron; undocumented firmware-4.19 registers are deliberately omitted.
HEX_NUMBERS: Dict[str, Dict[str, Any]] = {
    "battery_capacity":       {"id": 0x1000, "type": "u16", "scale": 1.0,  "name": "Batteriekapazität", "min": 1,   "max": 9999, "step": 1,    "unit": "Ah",  "icon": "mdi:battery"},
    "charged_voltage":        {"id": 0x1001, "type": "u16", "scale": 0.1,  "name": "Voll-Ladespannung", "min": 0,   "max": 95,   "step": 0.1,  "unit": "V",   "icon": "mdi:battery-charging"},
    "tail_current":           {"id": 0x1002, "type": "u16", "scale": 0.1,  "name": "Schweifstrom", "min": 0.5, "max": 10,   "step": 0.1,  "unit": "%",   "icon": "mdi:current-dc"},
    "charged_detection_time": {"id": 0x1003, "type": "u16", "scale": 1.0,  "name": "Erkennungszeit voll", "min": 1,   "max": 50,   "step": 1,    "unit": "min", "icon": "mdi:timer-check"},
    "charge_efficiency":      {"id": 0x1004, "type": "u16", "scale": 1.0,  "name": "Ladewirkungsgrad", "min": 50,  "max": 99,   "step": 1,    "unit": "%",   "icon": "mdi:percent"},
    "peukert_coefficient":    {"id": 0x1005, "type": "u16", "scale": 0.01, "name": "Peukert-Faktor", "min": 1.0, "max": 1.5,  "step": 0.01, "unit": None,  "icon": "mdi:function-variant"},
    "current_threshold":      {"id": 0x1006, "type": "u16", "scale": 0.01, "name": "Stromschwelle", "min": 0,   "max": 2,    "step": 0.01, "unit": "A",   "icon": "mdi:current-dc"},
    "ttg_delta_t":            {"id": 0x1007, "type": "u16", "scale": 1.0,  "name": "Restlaufzeit Mittelungszeit", "min": 0, "max": 12, "step": 1, "unit": "min", "icon": "mdi:timer-sand"},
    "discharge_floor":        {"id": 0x1008, "type": "u16", "scale": 0.1,  "name": "Entladegrenze", "min": 0,   "max": 99,   "step": 0.1,  "unit": "%",   "icon": "mdi:battery-low"},

    "alarm_low_voltage":       {"id": 0x0320, "type": "u16", "scale": 0.01, "name": "Alarm Unterspannung", "min": 0, "max": 95, "step": 0.1, "unit": "V", "icon": "mdi:alert-arrow-down"},
    "alarm_low_voltage_clear": {"id": 0x0321, "type": "u16", "scale": 0.01, "name": "Alarm Unterspannung zurücksetzen", "min": 0, "max": 95, "step": 0.1, "unit": "V", "icon": "mdi:alert-arrow-down-outline"},
    "alarm_high_voltage":      {"id": 0x0322, "type": "u16", "scale": 0.01, "name": "Alarm Überspannung", "min": 0, "max": 95, "step": 0.1, "unit": "V", "icon": "mdi:alert-arrow-up"},
    "alarm_high_voltage_clear":{"id": 0x0323, "type": "u16", "scale": 0.01, "name": "Alarm Überspannung zurücksetzen", "min": 0, "max": 95, "step": 0.1, "unit": "V", "icon": "mdi:alert-arrow-up-outline"},
    "alarm_low_starter":       {"id": 0x0324, "type": "u16", "scale": 0.01, "name": "Alarm Starterbatterie Unterspannung", "min": 0, "max": 95, "step": 0.1, "unit": "V", "icon": "mdi:car-battery"},
    "alarm_low_starter_clear": {"id": 0x0325, "type": "u16", "scale": 0.01, "name": "Starter Unterspannung zurücksetzen", "min": 0, "max": 95, "step": 0.1, "unit": "V", "icon": "mdi:car-battery"},
    "alarm_high_starter":      {"id": 0x0326, "type": "u16", "scale": 0.01, "name": "Alarm Starterbatterie Überspannung", "min": 0, "max": 95, "step": 0.1, "unit": "V", "icon": "mdi:car-battery"},
    "alarm_high_starter_clear":{"id": 0x0327, "type": "u16", "scale": 0.01, "name": "Starter Überspannung zurücksetzen", "min": 0, "max": 95, "step": 0.1, "unit": "V", "icon": "mdi:car-battery"},
    "alarm_low_soc":           {"id": 0x0328, "type": "u16", "scale": 0.1, "name": "Alarm niedriger Ladezustand", "min": 0, "max": 99, "step": 0.1, "unit": "%", "icon": "mdi:battery-alert"},
    "alarm_low_soc_clear":     {"id": 0x0329, "type": "u16", "scale": 0.1, "name": "Alarm Ladezustand zurücksetzen", "min": 0, "max": 99, "step": 0.1, "unit": "%", "icon": "mdi:battery-check"},
}

AUX_OPTIONS = {0: "Starterbatterie", 1: "Mittelpunkt", 2: "Temperatur"}
DC_MONITOR_OPTIONS = {
    -9: "Solarladeregler", -8: "Windturbine", -7: "Wellengenerator", -6: "Lichtmaschine",
    -5: "Brennstoffzelle", -4: "Wassergenerator", -3: "DC/DC-Ladegerät", -2: "AC-Ladegerät",
    -1: "Generische Quelle", 0: "Batteriemonitor", 1: "Generische Last", 2: "Elektroantrieb",
    3: "Kühlschrank", 4: "Wasserpumpe", 5: "Bilgepumpe", 6: "DC-System", 7: "Wechselrichter", 8: "Warmwasserbereiter",
}
HEX_SELECTS: Dict[str, Dict[str, Any]] = {
    "auxiliary_input": {"id": 0xEEF8, "type": "u8",  "name": "AUX-Eingang", "options": AUX_OPTIONS, "icon": "mdi:swap-horizontal"},
    "dc_monitor_mode": {"id": 0xEEB8, "type": "s16", "name": "DC-Monitor-Modus", "options": DC_MONITOR_OPTIONS, "icon": "mdi:tune-variant"},
    "start_synchronized": {"id": 0x0FFD, "type": "u8", "name": "Ladezustand bei Neustart", "options": {0: "Löschen", 1: "Auf 100 % setzen", 2: "Beibehalten"}, "icon": "mdi:sync"},
}
HEX_READ_ONLY: Dict[str, Dict[str, Any]] = {
    "synchronization_state": {"id": 0xEEB6, "type": "u8", "scale": 1.0, "name": "Synchronisationsstatus", "unit": None, "icon": "mdi:sync-circle"},
}
HEX_ACTIONS: Dict[str, Dict[str, Any]] = {
    "synchronize": {"id": 0x102C, "name": "Ladezustand auf 100 % synchronisieren", "icon": "mdi:battery-sync", "enabled": True},
    "alarm_acknowledge": {"id": 0x031F, "name": "Alarm quittieren", "icon": "mdi:alert-circle-check", "enabled": True},
    "zero_current": {"id": 0x1029, "name": "Nullstrom kalibrieren", "icon": "mdi:current-dc", "enabled": False},
    "clear_history": {"id": 0x1030, "name": "SmartShunt-Historie löschen", "icon": "mdi:history", "enabled": False},
}
HEX_POLL_KEYS = list(HEX_NUMBERS) + list(HEX_SELECTS) + list(HEX_READ_ONLY)
HEX_REFRESH_QUEUE = []
HEX_RUNTIME_AVAILABLE: Optional[bool] = None
HEX_LAST_ACTIVITY_TS = 0.0


def hex_build_frame(command: int, register_id: int, value_bytes: bytes = b"", flags: int = 0) -> bytes:
    data = struct.pack("<H", int(register_id)) + bytes([int(flags) & 0xFF]) + value_bytes
    checksum = (0x55 - (int(command) & 0x0F) - sum(data)) & 0xFF
    return b":" + f"{command:X}".encode("ascii") + data.hex().upper().encode("ascii") + f"{checksum:02X}".encode("ascii") + b"\n"


def hex_parse_frame(line: bytes) -> Optional[Dict[str, Any]]:
    raw = line.strip()
    if len(raw) < 10 or not raw.startswith(b":"):
        return None
    try:
        command = int(chr(raw[1]), 16)
        encoded = raw[2:]
        if len(encoded) % 2:
            return None
        packet = bytes.fromhex(encoded.decode("ascii"))
        if len(packet) < 4:
            return None
        body, checksum = packet[:-1], packet[-1]
        if ((command + sum(body) + checksum) & 0xFF) != 0x55:
            logger.warning("HEX Prüfsummenfehler: %s", raw.decode("ascii", errors="replace"))
            return None
        register_id = struct.unpack("<H", body[:2])[0]
        flags = body[2]
        return {"command": command, "id": register_id, "flags": flags, "value": body[3:]}
    except Exception:
        return None


def hex_codec_selftest() -> None:
    # Exact frames from Victron BMV-7xx HEX Protocol examples.
    if hex_build_frame(7, 0x1000) != b":70010003E\n":
        raise RuntimeError("VE.Direct HEX GET codec self-test failed")
    if hex_build_frame(8, 0x1000, struct.pack("<H", 500)) != b":8001000F40148\n":
        raise RuntimeError("VE.Direct HEX SET codec self-test failed")


def hex_meta_for_key(key: str) -> Optional[Dict[str, Any]]:
    return HEX_NUMBERS.get(key) or HEX_SELECTS.get(key) or HEX_READ_ONLY.get(key)


def hex_decode_value(meta: Dict[str, Any], raw: bytes) -> Any:
    typ = meta["type"]
    sizes = {"u8": 1, "u16": 2, "s16": 2, "u32": 4, "s32": 4}
    if len(raw) < sizes[typ]:
        raise ValueError(f"zu kurze HEX-Antwort für {typ}: {raw.hex()}")
    fmt = {"u8": "<B", "u16": "<H", "s16": "<h", "u32": "<I", "s32": "<i"}[typ]
    value = struct.unpack(fmt, raw[:sizes[typ]])[0]
    if "options" in meta:
        return meta["options"].get(value, f"Unbekannt ({value})")
    scale = float(meta.get("scale", 1.0))
    value = value * scale
    if scale < 1:
        decimals = 2 if scale <= 0.01 else 1
        return round(value, decimals)
    return int(value) if float(value).is_integer() else value


def hex_encode_value(meta: Dict[str, Any], user_value: Any) -> bytes:
    typ = meta["type"]
    if "options" in meta:
        reverse = {label: raw for raw, label in meta["options"].items()}
        if str(user_value) not in reverse:
            raise ValueError(f"ungültige Auswahl {user_value!r}")
        raw_value = int(reverse[str(user_value)])
    else:
        value = float(user_value)
        min_v, max_v = float(meta["min"]), float(meta["max"])
        if value < min_v - 1e-9 or value > max_v + 1e-9:
            raise ValueError(f"Wert {value} außerhalb {min_v}..{max_v}")
        raw_value = int(round(value / float(meta.get("scale", 1.0))))
    fmt = {"u8": "<B", "u16": "<H", "s16": "<h", "u32": "<I", "s32": "<i"}[typ]
    return struct.pack(fmt, raw_value)


def publish_hex_settings() -> None:
    mqtt_publish(config.get("settings_topic", "victron/shunt/settings"), HEX_SETTINGS_STATE, retain=True)


def hex_update_state(key: str, response: Dict[str, Any]) -> bool:
    meta = hex_meta_for_key(key)
    if not meta:
        return False
    flags = int(response.get("flags", 0))
    if flags:
        meanings = []
        if flags & 0x01: meanings.append("unbekannte Register-ID")
        if flags & 0x02: meanings.append("nicht unterstützt/schreibgeschützt")
        if flags & 0x04: meanings.append("Parameterfehler")
        logger.warning("HEX %s 0x%04X Fehler flags=0x%02X (%s)", key, meta["id"], flags, ", ".join(meanings) or "unbekannt")
        return False
    value = hex_decode_value(meta, response.get("value", b""))
    if key == "synchronization_state":
        value = "Synchronisiert" if int(value) else "Nicht synchronisiert"
    HEX_SETTINGS_STATE[key] = value
    publish_hex_settings()
    return True


def hex_prepare_mode(ser: serial.Serial) -> None:
    """Wake/switch SmartShunt from periodic TEXT mode into HEX mode when idle.

    SmartShunt firmware 4.19 on the official VE.Direct USB interface requires
    the regular Product-ID command (:451) before register GET/SET after TEXT
    mode has resumed. A direct hardware probe confirmed this behavior.
    """
    global HEX_LAST_ACTIVITY_TS
    now = time.time()
    if now - HEX_LAST_ACTIVITY_TS < 2.0:
        return
    ser.write(b":451\n")
    ser.flush()
    # Give the device time to finish the active TEXT frame and enter HEX mode.
    time.sleep(0.5)
    HEX_LAST_ACTIVITY_TS = time.time()


def hex_transaction(ser: serial.Serial, command: int, register_id: int, value_bytes: bytes = b"") -> Optional[Dict[str, Any]]:
    global HEX_LAST_ACTIVITY_TS
    hex_prepare_mode(ser)
    frame = hex_build_frame(command, register_id, value_bytes)
    timeout_s = float(config.get("hex_command_timeout_s", 1.5))
    old_timeout = ser.timeout
    deadline = time.time() + timeout_s
    try:
        ser.timeout = min(0.2, timeout_s)
        ser.write(frame)
        ser.flush()
        HEX_LAST_ACTIVITY_TS = time.time()
        while RUNNING and time.time() < deadline:
            line = ser.readline()
            if not line:
                continue
            if line.startswith(b":"):
                response = hex_parse_frame(line)
                if not response:
                    continue
                # Asynchronous HEX frames can arrive while waiting. Consume matching
                # command/id; other frames are harmless and the next refresh reads them again.
                if response.get("id") == register_id and response.get("command") in (command, 0xA):
                    return response
            # Normal VE.Direct text lines read during this short transaction are skipped;
            # merged text state keeps the last known values and the next frame refreshes them.
        logger.warning("HEX Timeout command=%X register=0x%04X", command, register_id)
        return None
    finally:
        ser.timeout = old_timeout


def hex_get_key(ser: serial.Serial, key: str) -> bool:
    meta = hex_meta_for_key(key)
    if not meta:
        return False
    response = hex_transaction(ser, 7, int(meta["id"]))
    return bool(response and hex_update_state(key, response))


def hex_set_key(ser: serial.Serial, key: str, user_value: Any) -> bool:
    meta = HEX_NUMBERS.get(key) or HEX_SELECTS.get(key)
    if not meta:
        logger.warning("Unbekannter oder nicht schreibbarer HEX-Key: %s", key)
        return False
    try:
        encoded = hex_encode_value(meta, user_value)
    except Exception as e:
        logger.warning("HEX SET %s abgelehnt: %s", key, e)
        return False
    response = hex_transaction(ser, 8, int(meta["id"]), encoded)
    if not response or not hex_update_state(key, response):
        return False
    logger.info("SmartShunt Einstellung geschrieben: %s=%s", key, HEX_SETTINGS_STATE.get(key))
    # Read back once; this also verifies that the device persisted the value.
    time.sleep(0.05)
    hex_get_key(ser, key)
    return True


def hex_run_action(ser: serial.Serial, key: str) -> bool:
    meta = HEX_ACTIONS.get(key)
    if not meta:
        logger.warning("Unbekannte HEX-Aktion: %s", key)
        return False
    response = hex_transaction(ser, 8, int(meta["id"]), b"")
    if not response:
        return False
    flags = int(response.get("flags", 0))
    if flags:
        logger.warning("HEX Aktion %s fehlgeschlagen, flags=0x%02X", key, flags)
        return False
    logger.info("SmartShunt Aktion ausgeführt: %s", key)
    return True


def process_hex_commands(ser: serial.Serial) -> None:
    try:
        command = HEX_COMMAND_QUEUE.get_nowait()
    except queue.Empty:
        return
    try:
        if command.get("op") == "set":
            hex_set_key(ser, str(command.get("key")), command.get("value"))
        elif command.get("op") == "action":
            hex_run_action(ser, str(command.get("key")))
    except Exception as e:
        logger.warning("HEX Kommando fehlgeschlagen: %s", e)


def send_hex_discovery(prefix: str, device_info: Dict[str, Any]) -> None:
    settings_topic = str(config.get("settings_topic", "victron/shunt/settings"))
    cmd_base = str(config.get("command_base_topic", "victron/shunt/command")).rstrip("/")
    availability = config["availability_topic"]

    def common(name: str, uid: str, icon: str) -> Dict[str, Any]:
        return {
            "name": name,
            "unique_id": uid,
            "device": device_info,
            "icon": icon,
            "availability_topic": availability,
            "payload_available": "online",
            "payload_not_available": "offline",
            "entity_category": "config",
        }

    # Writable numeric settings plus mirrored readback sensors. The sensor copies
    # are intentional: Remote Home Assistant on the house instance currently mirrors
    # sensors, while number/select entities remain native to the Womo instance.
    for key, meta in HEX_NUMBERS.items():
        n = common(meta["name"], f"victron_shunt_hex_number_{key}", meta["icon"])
        n.update({
            "state_topic": settings_topic,
            "value_template": f"{{{{ value_json.{key} }}}}",
            "command_topic": f"{cmd_base}/set/{key}",
            "min": meta["min"], "max": meta["max"], "step": meta["step"], "mode": "box",
        })
        if meta.get("unit"):
            n["unit_of_measurement"] = meta["unit"]
        mqtt_publish(f"{prefix}/number/victron_shunt_hex_{key}/config", n, retain=True)

        r = common(meta["name"] + " (Einstellung)", f"victron_shunt_hex_sensor_{key}", meta["icon"])
        r.pop("entity_category", None)
        r.update({"state_topic": settings_topic, "value_template": f"{{{{ value_json.{key} }}}}"})
        if meta.get("unit"):
            r["unit_of_measurement"] = meta["unit"]
        mqtt_publish(f"{prefix}/sensor/victron_shunt_hex_setting_{key}/config", r, retain=True)

    for key, meta in HEX_SELECTS.items():
        sel = common(meta["name"], f"victron_shunt_hex_select_{key}", meta["icon"])
        sel.update({
            "state_topic": settings_topic,
            "value_template": f"{{{{ value_json.{key} }}}}",
            "command_topic": f"{cmd_base}/set/{key}",
            "options": list(meta["options"].values()),
        })
        mqtt_publish(f"{prefix}/select/victron_shunt_hex_{key}/config", sel, retain=True)
        r = common(meta["name"] + " (Einstellung)", f"victron_shunt_hex_sensor_{key}", meta["icon"])
        r.pop("entity_category", None)
        r.update({"state_topic": settings_topic, "value_template": f"{{{{ value_json.{key} }}}}"})
        mqtt_publish(f"{prefix}/sensor/victron_shunt_hex_setting_{key}/config", r, retain=True)

    for key, meta in HEX_READ_ONLY.items():
        r = common(meta["name"], f"victron_shunt_hex_sensor_{key}", meta["icon"])
        r.pop("entity_category", None)
        r.update({"state_topic": settings_topic, "value_template": f"{{{{ value_json.{key} }}}}"})
        mqtt_publish(f"{prefix}/sensor/victron_shunt_hex_{key}/config", r, retain=True)

    hs = common("HEX Kommunikation", "victron_shunt_hex_sensor_hex_status", "mdi:serial-port")
    hs.pop("entity_category", None)
    hs.update({"state_topic": settings_topic, "value_template": "{{ value_json.hex_status }}"})
    mqtt_publish(f"{prefix}/sensor/victron_shunt_hex_status/config", hs, retain=True)

    for key, meta in HEX_ACTIONS.items():
        b = common(meta["name"], f"victron_shunt_hex_button_{key}", meta["icon"])
        b.update({"command_topic": f"{cmd_base}/action/{key}", "payload_press": "PRESS"})
        if not meta.get("enabled", True):
            b["enabled_by_default"] = False
        mqtt_publish(f"{prefix}/button/victron_shunt_hex_{key}/config", b, retain=True)


# Strict UX formatting: 2 decimals for the requested fields
FIELD_PRECISION: Dict[str, int] = {
    "voltage": 2,
    "starter_voltage": 2,
    "midpoint_voltage": 2,
    "midpoint_deviation": 1,
    "battery_temperature": 1,
    "current": 2,
    "power": 2,
    "soc": 2,
    "consumed": 2,

    "hist_deepest_discharge": 2,
    "hist_last_discharge": 2,
    "hist_avg_discharge": 2,
    "hist_total_drawn": 2,

    "hist_min_voltage": 2,
    "hist_max_voltage": 2,
    "hist_min_aux_voltage": 2,
    "hist_max_aux_voltage": 2,

    "hist_discharged_energy": 2,
    "hist_charged_energy": 2,

    "power_from_vi": 2,

    "consumed_energy_est_kwh": 2,
    "hist_total_drawn_energy_est_kwh": 2,
    "hist_deepest_discharge_energy_est_kwh": 2,
    "hist_last_discharge_energy_est_kwh": 2,
    "hist_avg_discharge_energy_est_kwh": 2,
}

LIVE_SOURCE_KEYS = {"V", "VS", "I", "P", "SOC", "CE", "TTG", "Alarm", "AR", "FW", "BMV", "PID", "SER#", "MON"}
HISTORY_SOURCE_KEYS = {k for k in MAPPING.keys() if k.startswith("H")}

def round_payload_values(payload: Dict[str, Any]) -> Dict[str, Any]:
    for field in list(payload.keys()):
        payload[field] = round_field(field, payload[field])
    return payload

def add_derived_values(payload: Dict[str, Any]) -> None:
    vbat = payload.get("voltage")
    curr = payload.get("current")
    if vbat is not None and curr is not None:
        try:
            payload["power_from_vi"] = float(vbat) * float(curr)
        except Exception:
            payload["power_from_vi"] = None

    payload["consumed_energy_est_kwh"] = ah_to_kwh_est(payload.get("consumed"), vbat)
    payload["hist_total_drawn_energy_est_kwh"] = ah_to_kwh_est(payload.get("hist_total_drawn"), vbat)
    payload["hist_deepest_discharge_energy_est_kwh"] = ah_to_kwh_est(payload.get("hist_deepest_discharge"), vbat)
    payload["hist_last_discharge_energy_est_kwh"] = ah_to_kwh_est(payload.get("hist_last_discharge"), vbat)
    payload["hist_avg_discharge_energy_est_kwh"] = ah_to_kwh_est(payload.get("hist_avg_discharge"), vbat)

    try:
        curr_f = float(payload.get("current")) if payload.get("current") is not None else None
    except Exception:
        curr_f = None
    payload["system_status"] = compute_system_status(curr_f)

def round_field(field: str, value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, bool) or isinstance(value, int) or isinstance(value, str):
        return value
    if isinstance(value, float):
        d = FIELD_PRECISION.get(field)
        return round(value, d) if d is not None else value
    return value

def convert_value(key: str, raw_value: str) -> Any:
    entry = MAPPING.get(key)
    if not entry:
        return raw_value
    _field, factor, typ = entry
    if typ != "str" and str(raw_value).strip() == "---":
        return None
    try:
        if typ == "str":
            return raw_value
        if typ == "int":
            val = int(float(raw_value))
            if key == "TTG" and val == -1:
                return None
            return val
        val = float(raw_value)
        if factor is not None:
            val *= float(factor)
        return val
    except Exception:
        return raw_value

def compute_system_status(current_a: Optional[float]) -> str:
    thr = float(config.get("status_threshold_a", 0.1))
    if current_a is None:
        return "Unbekannt"
    if current_a > thr:
        return "Laden"
    if current_a < -thr:
        return "Entladen"
    return "Leerlauf"

def ah_to_kwh_est(ah: Optional[float], voltage_v: Optional[float]) -> Optional[float]:
    if ah is None or voltage_v is None:
        return None
    try:
        return (float(ah) * float(voltage_v)) / 1000.0
    except Exception:
        return None

def send_discovery() -> None:
    logger.info("Sende MQTT Discovery (v%s)...", config.get("sw_version", "unknown"))
    prefix = str(config.get("discovery_prefix", "homeassistant")).strip("/")
    state_topic = config["state_topic"]

    device_info = {
        "identifiers": [config["device_id"]],
        "name": config["device_name"],
        "manufacturer": "Victron Energy",
        "model": "SmartShunt 300A",
        "sw_version": config["sw_version"],
    }

    sensors = [
        # Live
        ("voltage", "Aufbaubatterie Spannung", "V", "voltage", "mdi:car-battery"),
        ("starter_voltage", "Starterbatterie Spannung", "V", "voltage", "mdi:car-battery"),
        ("midpoint_voltage", "Batterie Mittelpunktspannung", "V", "voltage", "mdi:battery-heart-variant"),
        ("midpoint_deviation", "Batterie Mittelpunktabweichung", "%", None, "mdi:scale-balance"),
        ("battery_temperature", "Batterietemperatur", "°C", "temperature", "mdi:thermometer"),
        ("current", "Strom aktuell", "A", "current", "mdi:current-dc"),
        ("power", "Leistung aktuell", "W", "power", "mdi:flash"),
        ("power_from_vi", "Leistung (berechnet aus V×I)", "W", "power", "mdi:calculator"),
        ("soc", "Ladezustand", "%", "battery", "mdi:battery-high"),
        ("ttg", "Restlaufzeit", "min", "duration", "mdi:timer-sand"),
        ("system_status", "System Status", None, None, "mdi:swap-horizontal"),
        ("consumed", "Verbrauchte Kapazität seit Voll-Ladung", "Ah", None, "mdi:battery-minus"),
        ("consumed_energy_est_kwh", "Verbrauchte Energie seit Voll-Ladung (geschätzt)", "kWh", "energy", "mdi:flash"),

        # Alarm / device
        ("alarm", "Alarm Status", None, None, "mdi:alert-circle"),
        ("alarm_reason", "Alarm Grund", None, None, "mdi:alert-circle-outline"),
        ("model_name", "Modellbezeichnung", None, None, "mdi:information-outline"),
        ("fw_version", "Firmware Version", None, None, "mdi:chip"),
        ("fw_version_extended", "Firmware Version erweitert", None, None, "mdi:chip"),
        ("product_id", "Produkt-ID", None, None, "mdi:identifier"),
        ("serial", "Seriennummer", None, None, "mdi:barcode"),
        ("monitor_mode", "Monitor-Modus", None, None, "mdi:tune-variant"),

        # History
        ("hist_deepest_discharge", "Tiefste Entladung", "Ah", None, "mdi:chart-line-variant"),
        ("hist_deepest_discharge_energy_est_kwh", "Tiefste Entladung (geschätzt in kWh)", "kWh", "energy", "mdi:flash"),
        ("hist_last_discharge", "Letzte Entladung", "Ah", None, "mdi:chart-line-variant"),
        ("hist_last_discharge_energy_est_kwh", "Letzte Entladung (geschätzt in kWh)", "kWh", "energy", "mdi:flash"),
        ("hist_avg_discharge", "Durchschnittliche Entladung", "Ah", None, "mdi:chart-line-variant"),
        ("hist_avg_discharge_energy_est_kwh", "Durchschnittliche Entladung (geschätzt in kWh)", "kWh", "energy", "mdi:flash"),
        ("hist_total_drawn", "Gesamt entnommene Kapazität", "Ah", None, "mdi:battery-minus"),
        ("hist_total_drawn_energy_est_kwh", "Gesamt entnommene Energie (geschätzt)", "kWh", "energy", "mdi:flash"),

        ("hist_discharged_energy", "Gesamt entladene Energie", "kWh", "energy", "mdi:lightning-bolt"),
        ("hist_charged_energy", "Gesamt geladene Energie", "kWh", "energy", "mdi:lightning-bolt-outline"),

        ("hist_cycles", "Anzahl Ladezyklen", None, None, "mdi:counter"),
        ("hist_full_discharges", "Anzahl volle Entladungen", None, None, "mdi:counter"),
        ("hist_low_voltage_alarms", "Anzahl Unterspannungs-Alarme", None, None, "mdi:alert"),
        ("hist_high_voltage_alarms", "Anzahl Überspannungs-Alarme", None, None, "mdi:alert"),

        ("hist_min_voltage", "Minimale Spannung (Historie)", "V", "voltage", "mdi:arrow-down-bold"),
        ("hist_max_voltage", "Maximale Spannung (Historie)", "V", "voltage", "mdi:arrow-up-bold"),
        ("hist_min_aux_voltage", "Starter Min Spannung (Historie)", "V", "voltage", "mdi:car-battery"),
        ("hist_max_aux_voltage", "Starter Max Spannung (Historie)", "V", "voltage", "mdi:car-battery"),

        ("hist_time_since_full", "Zeit seit letzter Voll-Ladung", "s", "duration", "mdi:clock-outline"),
        ("hist_sync_count", "Anzahl Synchronisationen", None, None, "mdi:counter"),
    ]

    for uid, name, unit, dev_class, icon in sensors:
        topic = f"{prefix}/sensor/victron_shunt_{uid}/config"
        payload: Dict[str, Any] = {
            "name": name,
            "state_topic": state_topic,
            "value_template": f"{{{{ value_json.{uid} }}}}",
            "unique_id": f"victron_shunt_{uid}_usb_v404",
            "device": device_info,
            "icon": icon,
            "availability_topic": config["availability_topic"],
            "payload_available": "online",
            "payload_not_available": "offline",
        }
        if unit:
            payload["unit_of_measurement"] = unit
        if dev_class:
            payload["device_class"] = dev_class
        mqtt_publish(topic, payload, retain=True)

    if bool(config.get("hex_enabled", False)):
        send_hex_discovery(prefix, device_info)

def open_serial() -> serial.Serial:
    dev = str(config["serial_device"])
    baud = int(config.get("baudrate", 19200))
    timeout = float(config.get("serial_timeout_s", 1))

    if not os.path.exists(dev):
        raise FileNotFoundError(f"Serial Device nicht gefunden: {dev}")

    ser = serial.Serial(
        dev,
        baudrate=baud,
        timeout=timeout,
        xonxoff=False,
        rtscts=False,
        dsrdtr=False,
    )
    # Keep DTR/RTS asserted. With the official Victron VE.Direct USB cable
    # deasserting both lines still allowed RX text data but blocked host->Shunt HEX traffic.
    try:
        ser.setDTR(True)
        ser.setRTS(True)
    except Exception:
        pass
    try:
        ser.reset_input_buffer()
    except Exception:
        pass
    return ser

def read_loop() -> None:
    global HEX_RUNTIME_AVAILABLE
    ser: Optional[serial.Serial] = None
    frame_raw: Dict[str, str] = {}
    last_data_ts = time.time()
    last_summary_ts = 0.0
    last_hex_refresh_ts = 0.0

    seen_keys = set()
    unknown_keys = set()
    raw_line_count = 0
    frame_count = 0
    last_payload: Dict[str, Any] = {}
    merged_payload: Dict[str, Any] = {}
    merged_raw: Dict[str, str] = {}
    last_frame_keys = []
    warned_missing_live_once = False
    first_line_logged = False
    first_frame_logged = False

    while RUNNING:
        if ser is None:
            try:
                mqtt_publish(config["availability_topic"], "offline", retain=True)
                ser = open_serial()
                logger.info(f"Serial Port offen ({config['serial_device']}). Warte auf VE.Direct-Daten ...")
                last_data_ts = time.time()
                first_line_logged = False
                if bool(config.get("hex_enabled", False)):
                    # Probe one harmless register first. Only if that succeeds do we
                    # read the remaining settings. This prevents a dead TX path from
                    # causing a long chain of timeouts and interrupting text telemetry.
                    HEX_RUNTIME_AVAILABLE = None
                    HEX_REFRESH_QUEUE.clear()
                    HEX_REFRESH_QUEUE.append("battery_capacity")
                    last_hex_refresh_ts = time.time()
            except Exception as e:
                logger.error(f"Serial Fehler beim Öffnen: {e}")
                time.sleep(float(config.get("reconnect_wait_s", 2)))
                continue

        try:
            now = time.time()
            if bool(config.get("hex_enabled", False)):
                process_hex_commands(ser)
                refresh_s = max(300.0, float(config.get("hex_refresh_s", 3600)))
                if HEX_RUNTIME_AVAILABLE is True and not HEX_REFRESH_QUEUE and (now - last_hex_refresh_ts) >= refresh_s:
                    HEX_REFRESH_QUEUE.extend(HEX_POLL_KEYS)
                    last_hex_refresh_ts = now
                if HEX_REFRESH_QUEUE:
                    probe_key = HEX_REFRESH_QUEUE.pop(0)
                    probe_ok = hex_get_key(ser, probe_key)
                    if HEX_RUNTIME_AVAILABLE is None:
                        HEX_RUNTIME_AVAILABLE = bool(probe_ok)
                        HEX_SETTINGS_STATE["hex_status"] = "Verfügbar" if probe_ok else "Nicht verfügbar"
                        publish_hex_settings()
                        if probe_ok:
                            logger.info("VE.Direct HEX bidirektional verfügbar; lese Einstellungen ein.")
                            HEX_REFRESH_QUEUE.extend(k for k in HEX_POLL_KEYS if k != probe_key)
                            last_hex_refresh_ts = now
                        else:
                            logger.warning("VE.Direct HEX Rückkanal nicht verfügbar; weitere HEX-Abfragen bis zum nächsten Neustart ausgesetzt.")
                    now = time.time()

            # Count recent HEX traffic as serial activity: HEX temporarily pauses the TEXT stream.
            if HEX_LAST_ACTIVITY_TS > last_data_ts:
                last_data_ts = HEX_LAST_ACTIVITY_TS

            line_bytes = ser.readline()
            now = time.time()

            if not line_bytes:
                if now - last_data_ts > float(config.get("no_data_wakeup_s", 5)):
                    logger.warning(
                        "Keine VE.Direct-Daten seit %.1fs auf %s. Serial wird neu geöffnet.",
                        now - last_data_ts,
                        config["serial_device"],
                    )
                    mqtt_publish(config["availability_topic"], "offline", retain=True)
                    try:
                        if ser:
                            ser.close()
                    except Exception:
                        pass
                    ser = None
                    time.sleep(float(config.get("reconnect_wait_s", 2)))
                continue

            last_data_ts = now
            parsed = parse_vedirect_line(line_bytes)
            if not parsed:
                logger.debug("Ignoriere nicht auswertbare VE.Direct-Zeile: %s", safe_line_display(line_bytes))
                continue

            k, v = parsed
            raw_line_count += 1

            if not first_line_logged and k != "Checksum":
                logger.info("Erste VE.Direct-Zeile empfangen: %s", safe_line_display(line_bytes))
                first_line_logged = True

            if bool(config.get("publish_raw", False)) and k != "Checksum":
                mqtt_publish(
                    config["raw_topic"],
                    {"ts": int(now), "key": k, "value": v, "line": safe_line_display(line_bytes)},
                    retain=False,
                )

            if k == "Checksum":
                if not frame_raw:
                    continue

                frame_count += 1
                frame_payload: Dict[str, Any] = {}
                last_frame_keys = sorted(list(frame_raw.keys()))

                for rk, rv in frame_raw.items():
                    seen_keys.add(rk)
                    if rk in MAPPING:
                        field, _, _ = MAPPING[rk]
                        frame_payload[field] = convert_value(rk, rv)
                    else:
                        unknown_keys.add(rk)

                # Victron devices may emit frames that contain only history keys (H1-H18)
                # and separate frames that contain live keys (V/I/P/SOC/...).
                # The old v4.1.1 published each frame standalone. A history-only frame
                # therefore removed current, voltage and power from the MQTT JSON, making
                # Home Assistant show 0/unknown although the values existed in the previous frame.
                merged_payload.update(frame_payload)
                merged_raw.update(frame_raw)

                payload = dict(merged_payload)
                payload.setdefault("serial", "")
                for field, _, _ in MAPPING.values(): payload.setdefault(field, "")
                add_derived_values(payload)
                round_payload_values(payload)

                # Raw snapshots: full merged VE.Direct view plus the last completed frame.
                payload["_ve"] = dict(merged_raw)
                payload["_last_frame"] = dict(frame_raw)

                if not warned_missing_live_once and not any(k in frame_raw for k in ("V", "I", "P", "SOC")):
                    logger.info(
                        "VE.Direct-Frame ohne Live-Werte empfangen (%s). Werte werden mit letztem bekannten Frame zusammengeführt.",
                        ", ".join(last_frame_keys),
                    )
                    warned_missing_live_once = True

                # Sanity check
                if bool(config.get("log_power_sanity_check", True)):
                    try:
                        p = payload.get("power")
                        pvi = payload.get("power_from_vi")
                        if p is not None and pvi is not None:
                            delta = float(p) - float(pvi)
                            if abs(delta) > 2.0:
                                logger.warning(f"SanityCheck: P={p}W vs V*I={pvi}W (Δ={delta:.2f}W)")
                    except Exception:
                        pass

                last_payload = payload
                mqtt_publish(config["state_topic"], payload, retain=False)
                mqtt_publish(config["availability_topic"], "online", retain=True)
                if not first_frame_logged:
                    logger.info(
                        "Erster kompletter VE.Direct-Frame verarbeitet und nach %s veröffentlicht. Keys: %s",
                        config["state_topic"],
                        ", ".join(sorted([kk for kk in payload.keys() if kk != "_ve"])),
                    )
                    first_frame_logged = True
                frame_raw = {}

            else:
                frame_raw[k] = v

            # Summary
            if bool(config.get("publish_summary", True)) and (now - last_summary_ts) >= float(config.get("summary_interval_s", 60)):
                last_summary_ts = now
                summary = {
                    "ts": int(now),
                    "frames": frame_count,
                    "raw_lines": raw_line_count,
                    "seen_keys": sorted(list(seen_keys)),
                    "unknown_keys": sorted(list(unknown_keys)),
                    "last_frame_keys": last_frame_keys,
                    "last_payload_keys": sorted([kk for kk in last_payload.keys() if kk not in ("_ve", "_last_frame")]),
                }
                mqtt_publish(config["summary_topic"], summary, retain=False)

        except Exception as e:
            logger.error(f"Loop Fehler: {e}")
            mqtt_publish(config["availability_topic"], "offline", retain=True)
            try:
                if ser:
                    ser.close()
            except Exception:
                pass
            ser = None
            time.sleep(float(config.get("reconnect_wait_s", 2)))

def shutdown_cleanup(ser: Optional[serial.Serial] = None) -> None:
    try:
        mqtt_publish(config["availability_topic"], "offline", retain=True)
    except Exception:
        pass
    try:
        if ser:
            ser.close()
    except Exception:
        pass
    try:
        client.loop_stop()
    except Exception:
        pass
    try:
        client.disconnect()
    except Exception:
        pass
    logger.info("Beendet. MQTT offline gesetzt.")

def main() -> None:
    hex_codec_selftest()
    logger.info(
        "Start v%s | serial=%s baud=%s | state_topic=%s | discovery_prefix=%s",
        config.get("sw_version", "unknown"),
        config.get("serial_device"),
        config.get("baudrate"),
        config.get("state_topic"),
        config.get("discovery_prefix"),
    )
    if str(config.get("discovery_prefix", "homeassistant")).strip("/") != "homeassistant":
        logger.warning(
            "Discovery Prefix ist '%s'. Home Assistant Standard ist 'homeassistant'. "
            "Nur so lassen, wenn deine MQTT-Integration wirklich diesen Discovery Prefix nutzt.",
            config.get("discovery_prefix"),
        )
    connect_mqtt()
    if not RUNNING:
        shutdown_cleanup()
        return
    send_discovery()
    mqtt_publish(config["availability_topic"], "offline", retain=True)
    try:
        read_loop()
    finally:
        shutdown_cleanup()

if __name__ == "__main__":
    main()

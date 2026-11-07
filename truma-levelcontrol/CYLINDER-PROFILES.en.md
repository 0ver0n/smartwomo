# Adapting and calibrating different gas cylinders

Version 0.3.0 is calibrated to **one particular German 11 kg steel cylinder**. The Truma LevelControl hardware supports many steel and aluminum cylinders according to its manufacturer, but **our independent Home Assistant volume conversion is NOT automatically correct for every cylinder**. Selecting another cylinder size in the official Truma app does NOT update this integration's own geometry constants.

## What is measured?
The sensor reports liquid height in millimetres, ultrasound transit time and temperature. The integration estimates liquid volume, residual kilograms and percent using a simplified cylinder with rounded end caps. Its default conversion assumes roughly 1.96 litres of liquid propane per kilogram. Different gas mixes and bottle shapes will differ. **Do not use this output to control gas valves, detect leaks, operate heaters, or perform safety-critical cutoffs.**

## Customizing a cylinder
1. Back up the complete working `/config/custom_components/truma_levelcontrol/` folder. Cross-check an actual sensor reading with the official Truma app.
2. Find the dimensions for **your exact cylinder**: nominal gas mass in kg, the cylinder's **stamped WATER capacity in litres**, approximate **inside** diameter in mm and the shape/depth of the rounded cylinder ends. Outer dimensions are not identical to inner dimensions.
3. Use the offline tool included at `tools/calibrate_bottle.py`. It does not access Home Assistant, Bluetooth, the Internet or your source files. Example for the **existing 11 kg reference** (do not reuse these values for other cylinders):
   `python3 tools/calibrate_bottle.py --label "DE 11 kg steel" --nominal-kg 11 --water-l 27.2 --inner-diameter-mm 296 --cap-depth-mm 53.79639190 --max-valid-height-mm 360 --reference-height-mm 289 --reference-kg 9.2`
4. Transfer all proposed constants into **`custom_components/truma_levelcontrol/const.py`**: `BOTTLE_PROFILE`, `BOTTLE_NOMINAL_GAS_KG`, `BOTTLE_WATER_VOLUME_L`, `BOTTLE_INNER_RADIUS_MM`, `BOTTLE_EFFECTIVE_CAP_DEPTH_MM`, `BOTTLE_EFFECTIVE_INNER_HEIGHT_MM`, `MAX_VALID_LIQUID_HEIGHT_MM`, `PROPANE_LITERS_PER_KG`, and `PROPANE_DENSITY_KG_L`. Density must remain the reciprocal of the litres-per-kg setting. **Changing 11 to 5 alone does not calibrate a 5 kg bottle**.
5. The maximum valid liquid height is also part of the invalid-measurement guard. Never set it to an unlimited value or above the effective internal height; otherwise reflected or doubled ultrasound readings may appear valid.
6. This v0.3.0 integration uses **one global cylinder profile for all configured LevelControl devices**. Different cylinder sizes used simultaneously need a future per-device profile feature; this version cannot accurately calculate two different shapes at once.
7. Validate the Home Assistant configuration, then restart **Home Assistant Core** in a controlled way. Allow the first BLE reading (polling every 30 minutes). Compare height, percent, and kilograms with the official Truma app.
8. Check at least **two substantially different fill levels**, ideally one near full and another around half. If the results disagree, revise the geometry or gas density assumptions; matching one single point does not prove the entire curve. If the parameters cannot be reliably calibrated, report the raw height only and do not make accuracy claims about kg or percent.
9. If necessary, restore your original backed-up integration folder and restart Home Assistant Core. Keep a separate backup of custom constants before updating the extension.

## On every cylinder replacement
- Reattach the LevelControl according to Truma's instructions and **briefly press the button on the device** when changing the cylinder. If the cylinder type changes, update the official Truma app too. Neither action automatically changes this Home Assistant integration's constants.
- Steel cylinders use the magnetic attachment; aluminum cylinders need the manufacturer's clamp. The sensor is not approved for plastic cylinders or the tank/refillable formats excluded by Truma.
- If measurements stop arriving for 60–120 minutes, become `unavailable`, or BLE errors occur, check the batteries and reception first. A previously cached `OK` sensor can remain visible after the last valid measurement, so check the `last_reported` timestamp for the liquid height or percent sensor.
- Truma lists **two AAA batteries** for the device. Replace depleted sensor batteries before trying to solve hardware failures by editing Python code.

**Geometry disclaimer:** The helper derives an effective internal height from the bottle's water capacity, estimated internal radius and rounded-end depth. This is an approximation. Manufacturer data and at least two real reference readings remain essential.

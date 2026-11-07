#!/usr/bin/env python3
"""Offline bottle-profile helper for Truma LevelControl BLE.

This program does not connect to Home Assistant, Bluetooth or any gas device.
It calculates candidate constants for the approximate capsule geometry model.
A manufacturer-app comparison at multiple fill levels is still mandatory.
"""
from __future__ import annotations

import argparse
import math
import sys


def cap_volume_mm3(radius_mm: float, cap_depth_mm: float, liquid_height_mm: float) -> float:
    """Spherical-cap approximation, same model as coordinator.py v0.3.0."""
    sphere_radius = (radius_mm**2 + cap_depth_mm**2) / (2 * cap_depth_mm)
    h = min(cap_depth_mm, max(0.0, liquid_height_mm))
    return math.pi * h**2 * (3 * sphere_radius - h) / 3


def profile_height_mm(volume_l: float, radius_mm: float, cap_depth_mm: float) -> float:
    area = math.pi * radius_mm**2
    cap = cap_volume_mm3(radius_mm, cap_depth_mm, cap_depth_mm)
    return 2 * cap_depth_mm + (volume_l * 1_000_000 - 2 * cap) / area


def liquid_volume_l(height_mm: float, water_l: float, radius_mm: float,
                    cap_depth_mm: float, total_height_mm: float) -> float:
    y = min(total_height_mm, max(0.0, height_mm))
    cap = cap_volume_mm3(radius_mm, cap_depth_mm, cap_depth_mm)
    if y <= cap_depth_mm:
        mm3 = cap_volume_mm3(radius_mm, cap_depth_mm, y)
    elif y <= total_height_mm - cap_depth_mm:
        mm3 = cap + math.pi * radius_mm**2 * (y - cap_depth_mm)
    else:
        mm3 = water_l * 1_000_000 - cap_volume_mm3(
            radius_mm, cap_depth_mm, total_height_mm - y)
    return min(water_l, max(0.0, mm3 / 1_000_000))


def main() -> int:
    p = argparse.ArgumentParser(
        description="Estimate LevelControl profile constants; NOT a safety measurement.")
    p.add_argument("--label", required=True, help="Cylinder name (shown in HA)")
    p.add_argument("--nominal-kg", type=float, required=True)
    p.add_argument("--water-l", type=float, required=True,
                   help="Stamped WATER capacity, not the gas fill volume")
    p.add_argument("--inner-diameter-mm", type=float, required=True,
                   help="Estimated INSIDE diameter; outer diameter is not equivalent")
    p.add_argument("--cap-depth-mm", type=float, required=True,
                   help="Estimated effective depth of each rounded bottle end")
    p.add_argument("--max-valid-height-mm", type=float, required=True,
                   help="Reject physically impossible measurement heights")
    p.add_argument("--liters-per-kg", type=float, default=1.96,
                   help="Approximate LPG liquid liters/kg; default for propane")
    p.add_argument("--reference-height-mm", type=float, default=None,
                   help="Raw LevelControl height at a manufacturer-app reference reading")
    p.add_argument("--reference-kg", type=float, default=None,
                   help="Manufacturer app residual gas mass for that height")
    args = p.parse_args()
    vals = [args.nominal_kg, args.water_l, args.inner_diameter_mm,
            args.cap_depth_mm, args.max_valid_height_mm, args.liters_per_kg]
    if any(not math.isfinite(x) or x <= 0 for x in vals):
        p.error("All physical parameters must be positive finite numbers")
    radius = args.inner_diameter_mm / 2
    depth = args.cap_depth_mm
    if depth >= radius:
        p.error("cap depth must be smaller than inner radius")
    height = profile_height_mm(args.water_l, radius, depth)
    if not (2 * depth < height and args.max_valid_height_mm <= height):
        p.error("Inconsistent water volume/geometry or maximum valid height")
    if args.water_l < args.nominal_kg * args.liters_per_kg:
        p.error("Water capacity cannot be lower than liquid nominal gas volume")
    if (args.reference_height_mm is None) != (args.reference_kg is None):
        p.error("Provide reference height and reference mass together")
    print("# Suggested values for custom_components/truma_levelcontrol/const.py")
    print(f"BOTTLE_PROFILE = {args.label!r}")
    print(f"BOTTLE_NOMINAL_GAS_KG = {args.nominal_kg:.6f}")
    print(f"BOTTLE_WATER_VOLUME_L = {args.water_l:.6f}")
    print(f"BOTTLE_INNER_RADIUS_MM = {radius:.6f}")
    print(f"BOTTLE_EFFECTIVE_CAP_DEPTH_MM = {depth:.6f}")
    print(f"BOTTLE_EFFECTIVE_INNER_HEIGHT_MM = {height:.8f}")
    print(f"MAX_VALID_LIQUID_HEIGHT_MM = {args.max_valid_height_mm:.6f}")
    print(f"PROPANE_LITERS_PER_KG = {args.liters_per_kg:.6f}")
    print(f"PROPANE_DENSITY_KG_L = 1.0 / PROPANE_LITERS_PER_KG")
    if args.reference_height_mm is not None:
        if not 0 < args.reference_height_mm <= args.max_valid_height_mm:
            p.error("Reference height is outside the stated valid range")
        kg = min(args.nominal_kg, liquid_volume_l(
            args.reference_height_mm, args.water_l, radius, depth, height)
            / args.liters_per_kg)
        print(f"# Reference result: {kg:.2f} kg in model, "
              f"{args.reference_kg:.2f} kg in manufacturer app, "
              f"delta {kg-args.reference_kg:+.2f} kg")
        if abs(kg-args.reference_kg) > max(0.25, args.nominal_kg*0.05):
            print("# WARNING: geometry is not calibrated to this reference",
                  file=sys.stderr)
            return 2
    print("# WARNING: approximate geometry, verify at multiple levels against the app")
    return 0


if __name__ == "__main__":
    sys.exit(main())

#!/usr/bin/env bash
# Copy the controller firmware's planning code into energikalkyl.
#
#   bash controller/sync.sh ../norvi-energy-controller ../energy-scheduler-sim
#
# Firmware (norvi-energy-controller): the planner and its dependencies, used
# unchanged. Simulator (energy-scheduler-sim): wasm/batch.cpp, which runs the
# firmware's planning per day with run-time battery/fuse/EV settings, and its
# build glue. After syncing: python3 -m pytest -q -k controller
set -eu
FW="$(cd "${1:?firmware repo path}" && pwd)"
SIM="$(cd "${2:?simulator repo path}" && pwd)"
HERE="$(cd "$(dirname "$0")" && pwd)"
FW_SRC="battery_plan scheduler tariff fuse deye_program time_local"
FW_INC="battery_plan config deye_program deye_registers fuse scheduler tariff time_local tou_window"
rm -rf "$HERE/firmware" "$HERE/sim"
mkdir -p "$HERE/firmware/src" "$HERE/firmware/include" "$HERE/sim/emscripten"
for f in $FW_SRC; do cp "$FW/src/$f.cpp" "$HERE/firmware/src/"; done
for f in $FW_INC; do cp "$FW/include/$f.h" "$HERE/firmware/include/"; done
cp "$SIM/wasm/batch.cpp" "$SIM/wasm/sim_hal.h" "$SIM/wasm/sim_overrides.h" "$HERE/sim/"
cp "$SIM/wasm/native/emscripten/emscripten.h" "$HERE/sim/emscripten/"
{
    echo "firmware $(git -C "$FW" rev-parse HEAD) ($(git -C "$FW" rev-parse --abbrev-ref HEAD))"
    echo "simulator $(git -C "$SIM" rev-parse HEAD) ($(git -C "$SIM" rev-parse --abbrev-ref HEAD))"
} > "$HERE/VERSION"
cat "$HERE/VERSION"

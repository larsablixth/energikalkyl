#!/usr/bin/env bash
# Copy the NORVI controller firmware and the simulator's period runner into
# energikalkyl.
#
#   bash controller/sync.sh ../norvi-energy-controller ../energy-scheduler-sim
#
# Firmware (norvi-energy-controller): the controller (controller.cpp) and
# everything it runs — planner, pipeline, fuse guard, house model/learning,
# plant.h — used unchanged. Simulator (energy-scheduler-sim): the period
# runner (wasm/runner.cpp: moves the clock, feeds the days), its simulated
# devices (world.cpp, controller_hal.cpp, hal_stubs.cpp), the planner
# references (reference.cpp) and the build glue. Nothing here decides
# anything; the controller does. After syncing: python3 -m pytest -q -k controller
set -eu
FW="$(cd "${1:?firmware repo path}" && pwd)"
SIM="$(cd "${2:?simulator repo path}" && pwd)"
HERE="$(cd "$(dirname "$0")" && pwd)"
FW_SRC="$(make -s -C "$SIM" print-fw-sources ESP_SRC=src | xargs -n1 basename)"
SIM_FILES="runner.cpp world.cpp world.h controller_hal.cpp hal_stubs.cpp reference.cpp sim_devices.h sim_hal.h sim_overrides.h"
rm -rf "$HERE/firmware" "$HERE/sim"
mkdir -p "$HERE/firmware/src" "$HERE/firmware/include" "$HERE/sim/emscripten"
for f in $FW_SRC; do cp "$FW/src/$f" "$HERE/firmware/src/"; done
cp "$FW"/include/*.h "$HERE/firmware/include/"
for f in $SIM_FILES; do cp "$SIM/wasm/$f" "$HERE/sim/"; done
cp "$SIM/wasm/stubs/Arduino.h" "$HERE/sim/"
cp "$SIM/wasm/native/emscripten/emscripten.h" "$HERE/sim/emscripten/"
{
    echo "firmware $(git -C "$FW" rev-parse HEAD) ($(git -C "$FW" rev-parse --abbrev-ref HEAD))"
    echo "simulator $(git -C "$SIM" rev-parse HEAD) ($(git -C "$SIM" rev-parse --abbrev-ref HEAD))"
} > "$HERE/VERSION"
cat "$HERE/VERSION"

#include "plant.h"

namespace {
Plant g_plant;
}

const Plant& plant() { return g_plant; }
Plant* plant_mutable() { return &g_plant; }

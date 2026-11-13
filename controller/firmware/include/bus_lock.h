#pragma once
#include <cstdint>

// ── Shared network bus lock ──────────────────────────────────────────
// The W5500 Ethernet chip, the global EthernetClient in network.cpp and the
// ModbusTCP client in deye_modbus.cpp are used by several FreeRTOS tasks
// (scheduler, surplus, fuse guard). None of them are thread-safe, and the
// Deye dongle accepts only one Modbus TCP client, so every transaction goes
// through this ONE recursive mutex (recursive: deye_set_charge() holds it
// across several register writes).
//
// Usage:
//     BusLock lock;                 // waits up to BUS_LOCK_TIMEOUT_MS
//     if (!lock.ok()) return false; // treat as a failed transaction
//
// On native builds (no FreeRTOS) this compiles to no-ops that always succeed.

constexpr uint32_t BUS_LOCK_TIMEOUT_MS = 20000;  // > longest single transaction

// Create the mutex. Call once from setup() before starting tasks.
void bus_lock_init(void);
bool bus_lock_take(uint32_t timeout_ms);
void bus_lock_give(void);

class BusLock {
public:
    explicit BusLock(uint32_t timeout_ms = BUS_LOCK_TIMEOUT_MS)
        : ok_(bus_lock_take(timeout_ms)) {}
    ~BusLock() {
        if (ok_) {
            bus_lock_give();
        }
    }
    bool ok() const { return ok_; }
    BusLock(const BusLock&) = delete;
    BusLock& operator=(const BusLock&) = delete;
private:
    bool ok_;
};

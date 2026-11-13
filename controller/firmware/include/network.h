#pragma once
#include <cstdint>

// Initialize W5500 Ethernet with static IP from config.h.
// Must be called before any network operation.
bool network_init(void);

// Perform an HTTP GET and store the response body in buf.
// Returns number of body bytes, or -1 on failure. Failure includes: connect
// error, timeout before the server closed the connection, response larger
// than buf (truncated JSON is never handed to a parser), missing/invalid
// status line, or a non-2xx HTTP status. If http_status is given it receives
// the parsed status code (0 if none).
// Holds the shared bus lock (bus_lock.h) for the whole transaction and
// yields (delay(1)) while waiting, with wrap-safe millis() timing.
int network_http_get(const char* host, uint16_t port,
                     const char* path, char* buf, int buf_size,
                     unsigned long timeout_ms = 10000,
                     int* http_status = nullptr);

// HTTPS GET with certificate validation (ESP_SSLClient / BearSSL over a
// second EthernetClient socket). Trusted roots: entsoe_ca.h (ENTSO-E) and
// smhi_ca.h (SMHI). A host whose root is not in the list
// fails the handshake; refuses (returns -1) if no CA at all is configured or
// the system time is not valid. Same return contract as network_http_get().
// UNVERIFIED on hardware — see network.cpp.
int network_https_get(const char* host, uint16_t port,
                      const char* path, char* buf, int buf_size,
                      unsigned long timeout_ms = 15000,
                      int* http_status = nullptr);

// Send one UDP datagram and wait up to timeout_ms for one reply (SNTP).
// Returns the number of bytes received, -1 on failure/timeout.
int network_udp_exchange(const char* host, uint16_t port,
                         const uint8_t* tx, int tx_len,
                         uint8_t* rx, int rx_max, unsigned long timeout_ms);

// HTTPS POST (used by tibber_pulse.cpp). NOT implemented: the W5500 has no
// TLS and no TLS client library is in lib_deps yet. Always returns -1, so
// callers fail safe (the fuse guard treats it as "no meter data").
int network_https_post(const char* host, uint16_t port, const char* path,
                       const char* body, int body_len, const char* auth_header,
                       char* buf, int buf_size, unsigned long timeout_ms);

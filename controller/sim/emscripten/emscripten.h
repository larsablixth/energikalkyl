#pragma once
// Native stand-in for <emscripten/emscripten.h> — used ONLY for host builds
// of the binding layer (g++ -fsyntax-only, and the native driver in
// wasm/native/driver.cpp). Not used by `make` (emcc has the real header).
//
//   EMSCRIPTEN_KEEPALIVE  → nothing (all exported functions are extern "C")
//   EM_JS(ret, name, params, body)
//                         → `extern "C" ret name params;` — the JavaScript
//                           body is dropped and the native driver provides a
//                           C++ implementation of the same function. That is
//                           how the native driver plays the "JS world".
//   EM_ASM*               → no-ops (the binding layer does not use them; kept
//                           so stray uses still compile).
#define EMSCRIPTEN_KEEPALIVE
#define EM_JS(ret, name, params, ...) extern "C" ret name params;
#define EM_ASM(...) ((void)0)
#define EM_ASM_INT(...) 0
#define EM_ASM_DOUBLE(...) 0.0

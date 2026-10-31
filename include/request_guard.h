// Keeps the local server to requests from its own page.
//
// CORS only stops other sites reading a response: their POSTs still arrive. Checking Origin
// refuses those, and checking Host refuses DNS rebinding, where a hostile domain resolves
// to 127.0.0.1 and so looks like the same origin to the browser.
#pragma once

#include <string>

inline bool isLocalHost(const std::string &host) {
    return host == "localhost:8080" || host == "127.0.0.1:8080";
}

// A request without an Origin comes from curl or a same-origin GET, not from another site.
inline bool isLocalRequest(const std::string &host, const std::string &origin) {
    if (!isLocalHost(host)) return false;
    return origin.empty() || origin == "http://localhost:8080" ||
           origin == "http://127.0.0.1:8080";
}

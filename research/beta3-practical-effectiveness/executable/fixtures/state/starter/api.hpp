#pragma once
#include <string>
class Session {
public:
    bool ready() { return false; }
    bool send(const std::string&) { return true; }
    void close() {}
    void encrypted(bool) {}
    void retry(bool) {}
    bool encrypted() const { return false; }
    bool retry() const { return false; }
};

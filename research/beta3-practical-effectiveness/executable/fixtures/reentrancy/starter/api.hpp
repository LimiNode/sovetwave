#pragma once
#include <functional>
class Dispatcher {
public:
    void start(std::function<void()> callback) {}
    bool submit() { return false; }
    void request_stop() {}
    void join() {}
};

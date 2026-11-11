#pragma once
#include <condition_variable>
#include <functional>
#include <mutex>
#include <thread>
#include <utility>

class Dispatcher {
    std::mutex mutex;
    std::condition_variable ready;
    bool stopping = false;
    bool pending = false;
    std::thread worker;
public:
    // One start per instance; join is performed by the external coordinator.
    void start(std::function<void()> callback) {
        worker = std::thread([this, callback = std::move(callback)] {
            std::unique_lock<std::mutex> lock(mutex);
            ready.wait(lock, [this] { return pending || stopping; });
            if (pending) {
                pending = false;
                lock.unlock(); // call-out boundary
                callback();
            }
        });
    }
    bool submit() {
        std::lock_guard<std::mutex> lock(mutex);
        if (stopping) return false;
        pending = true; ready.notify_one(); return true;
    }
    void request_stop() { std::lock_guard<std::mutex> lock(mutex); stopping = true; ready.notify_one(); }
    void join() { if (worker.joinable()) worker.join(); }
    ~Dispatcher() { request_stop(); join(); }
};

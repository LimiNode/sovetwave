#include "api.hpp"
#include <cassert>
#include <future>

int main() {
    for (int i = 0; i < 3; ++i) {
        Dispatcher dispatcher;
        std::promise<void> completed;
        auto done = completed.get_future();
        dispatcher.start([&dispatcher, &completed] {
            dispatcher.request_stop(); // must not deadlock on worker's held lock
            completed.set_value();
        });
        assert(dispatcher.submit());
        done.get(); // entire executable has an external process timeout
        dispatcher.join();
        assert(!dispatcher.submit());
    }
    Dispatcher idle;
    idle.start([] {});
    idle.request_stop(); idle.join();
}

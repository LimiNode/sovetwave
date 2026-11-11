#include "api.hpp"
#include <cassert>
#include <type_traits>

int main() {
    static_assert(!std::is_copy_constructible_v<Source::Token>);
    int calls = 0;
    Source source;
    {
        auto first = source.subscribe([&calls] { ++calls; });
        source.publish(); assert(calls == 1);
        auto second = std::move(first);
        first.reset(); source.publish(); assert(calls == 2);
    }
    source.publish(); assert(calls == 2); // destruction prevents future delivery
    Source::Token self;
    self = source.subscribe([&self, &calls] { ++calls; self.reset(); });
    source.publish(); source.publish(); assert(calls == 3); // no self-wait
    self.reset(); self.reset(); // idempotence
    auto receiver = std::make_shared<int>(0);
    std::weak_ptr<int> weak = receiver;
    auto explicit_token = source.subscribe([weak] { if (auto target = weak.lock()) ++*target; });
    source.publish(); assert(*receiver == 1);
    explicit_token.reset(); // visible shutdown coordination remains supported
    receiver.reset(); source.publish(); assert(weak.expired());
    Source::Token survivor;
    { Source short_source; survivor = short_source.subscribe([] {}); }
    survivor.reset(); // token teardown after source destruction
}

#pragma once
#include <functional>
#include <map>
#include <memory>
#include <utility>

// Single-threaded synchronous delivery. A callback may unsubscribe itself.
class Source {
    struct State { int next = 0; std::map<int, std::function<void()>> callbacks; };
    std::shared_ptr<State> state = std::make_shared<State>();
public:
    class Token {
        std::weak_ptr<State> state;
        int id = 0;
    public:
        Token() = default;
        Token(std::shared_ptr<State> owner, int value) : state(owner), id(value) {}
        Token(const Token&) = delete;
        Token& operator=(const Token&) = delete;
        Token(Token&& other) noexcept : state(std::move(other.state)), id(other.id) {}
        Token& operator=(Token&& other) noexcept {
            if (this != &other) { reset(); state = std::move(other.state); id = other.id; }
            return *this;
        }
        ~Token() { reset(); }
        void reset() { if (auto owner = state.lock()) owner->callbacks.erase(id); state.reset(); }
    };
    Token subscribe(std::function<void()> callback) {
        int id = ++state->next;
        state->callbacks.emplace(id, std::move(callback));
        return Token(state, id);
    }
    void publish() {
        auto snapshot = state->callbacks;
        for (auto& [id, callback] : snapshot) {
            if (state->callbacks.count(id)) callback();
        }
    }
};

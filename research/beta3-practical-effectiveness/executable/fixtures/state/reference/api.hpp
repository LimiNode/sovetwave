#pragma once
#include <string>
class Session {
    enum class State { Connecting, Ready, Closed };
    State state = State::Connecting;
    bool encryption = false;
    bool retries = false;
public:
    bool ready() { if (state != State::Connecting) return false; state = State::Ready; return true; }
    bool send(const std::string& text) { return state == State::Ready && !text.empty() && text.size() <= 8; }
    void close() { state = State::Closed; }
    void encrypted(bool value) { encryption = value; }
    void retry(bool value) { retries = value; }
    bool encrypted() const { return encryption; }
    bool retry() const { return retries; }
};

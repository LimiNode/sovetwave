#pragma once
#include <functional>
#include <memory>

class Source {
public:
    class Token {
    public:
        Token() = default;
        Token(const Token&) = delete;
        Token& operator=(const Token&) = delete;
        Token(Token&&) = default;
        Token& operator=(Token&&) = default;
        void reset() {}
    };
    Token subscribe(std::function<void()> callback) { return {}; }
    void publish() {}
};

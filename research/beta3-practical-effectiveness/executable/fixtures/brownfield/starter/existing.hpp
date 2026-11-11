#pragma once
#include <charconv>
#include <string>
inline bool ParseNonNegative(const std::string& text, int& result) {
    int parsed = 0;
    auto last = text.data() + text.size();
    auto status = std::from_chars(text.data(), last, parsed);
    if (status.ec != std::errc{} || status.ptr != last || parsed < 0) return false;
    result = parsed; return true;
}

#pragma once
#include <filesystem>
#include <fstream>
#include <string>
// Root is pre-created and exclusively owned by the caller; concurrent path
// replacement is excluded. Only flat alphanumeric names plus '-' are allowed.
inline bool store(const std::filesystem::path& root, const std::string& name, const std::string& payload) {
    if (name.empty() || name.size() > 16 || payload.size() > 16) return false;
    for (unsigned char c : name) {
        if (!((c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') || c == '-')) return false;
    }
    auto target = root / name;
    if (std::filesystem::is_symlink(std::filesystem::symlink_status(target))) return false;
    std::ofstream stream(target, std::ios::binary);
    stream << payload; return stream.good();
}

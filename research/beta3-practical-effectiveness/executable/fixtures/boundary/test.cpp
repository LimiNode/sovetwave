#include "api.hpp"
#include <cassert>
#include <fstream>
#include <iterator>
namespace fs = std::filesystem;
static std::string read(const fs::path& path) {
    std::ifstream stream(path); return {std::istreambuf_iterator<char>(stream), {}};
}
int main(int argc, char** argv) {
    if (argc == 2) {
        // The external oracle creates root/sentinels before this invocation.
        assert(!store("trace-root", "../trace-outside", "evil"));
        return 0;
    }
    fs::create_directory("root");
    { std::ofstream stream("outside"); stream << "sentinel"; }
    fs::create_symlink("../outside", "root/link");
    assert(store("root", "safe-1", "ok")); assert(read("root/safe-1") == "ok");
    auto before = read("outside");
    assert(!store("root", "../outside", "evil"));
    assert(!store("root", "/work/outside", "evil"));
    assert(!store("root", "link", "evil"));
    assert(!store("root", "", "evil"));
    assert(!store("root", "safe-1", std::string(17, 'x')));
    assert(read("outside") == before); assert(read("root/safe-1") == "ok");
}

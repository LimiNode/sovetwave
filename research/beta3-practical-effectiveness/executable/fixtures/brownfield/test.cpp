#include "api.hpp"
#include <cassert>
int main() {
    Configuration config;
    int value = -1;
    assert(config.ParseValue("0", value) && value == 0);
    assert(config.ParseValue("101", value) && value == 101);
    for (auto text : {"", "-1", "2x", " 2", "9999999999999999999999999"}) {
        value = 17; assert(!config.ParseValue(text, value)); assert(value == 17);
    }
}

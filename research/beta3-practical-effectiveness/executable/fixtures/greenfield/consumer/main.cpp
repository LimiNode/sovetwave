#include <demo.hpp>
#include <cassert>
int main() {
    AudioPlayer player;
    assert(player.total() == 0);
    assert(player.add_sample(100)); assert(player.add_sample(-2));
    assert(player.total() == 98);
    assert(!player.add_sample(101)); assert(!player.add_sample(-101));
    assert(player.total() == 98);
}

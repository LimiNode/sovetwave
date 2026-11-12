#include "api.hpp"
#include <cassert>
int main() {
    Session session;
    assert(!session.send("a"));
    assert(session.ready()); assert(!session.ready());
    assert(session.send("12345678"));
    assert(!session.send("")); assert(!session.send("123456789"));
    session.encrypted(true); session.retry(true);
    assert(session.encrypted() && session.retry());
    session.encrypted(false); assert(!session.encrypted() && session.retry());
    session.close(); session.close();
    assert(!session.send("a")); assert(!session.ready());
    Session independent; assert(independent.ready()); assert(independent.send("a"));
}

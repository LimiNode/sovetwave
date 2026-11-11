#include <demo.hpp>
static_assert(sample_in_range(-100) && sample_in_range(100));
static_assert(!sample_in_range(-101) && !sample_in_range(101));
int main() {}

#include <demo.hpp>
bool AudioPlayer::add_sample(int sample) {
    if (!sample_in_range(sample)) return false;
    m_total += sample; return true;
}
int AudioPlayer::total() const { return m_total; }

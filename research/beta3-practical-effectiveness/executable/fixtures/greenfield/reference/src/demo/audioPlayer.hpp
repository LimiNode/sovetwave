#pragma once
/// \brief Small integer sample accumulator; accepts samples in [-100, 100].
class AudioPlayer {
    int m_total = 0;
public:
    /// \brief Add a sample, returning false without mutation if out of range.
    bool add_sample(int sample);
    /// \return The sum of the accepted samples.
    int total() const;
};

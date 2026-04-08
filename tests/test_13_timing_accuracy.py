"""
Test 13: Word timing must reflect actual TTS speech patterns.

Root cause of speed mismatch:
  estimate_word_segments() distributes time proportionally to character count.
  TTS doesn't work this way — it speaks at roughly constant word rate,
  spending similar time on "I" (1 char) and "because" (7 chars).
  Character-proportion causes short words to flash by and long words to linger.

Fix: use syllable count as the proportion metric.
  Syllables correlate much better with TTS duration than characters.
  "I" = 1 syllable, "because" = 2 syllables, "interesting" = 4 syllables.
  This approximates real speech cadence without external dependencies.

Acceptance criteria:
- count_syllables(word) exists in tts.engine
- Short function words ("I", "a", "the") get at least 1 syllable
- Multi-syllable words counted reasonably (beautiful=3, interesting=4)
- estimate_word_segments uses syllable-based distribution
- Short words get more relative time than character-proportion would give
"""
import pytest


def test_count_syllables_exists():
    from tts.engine import count_syllables
    assert callable(count_syllables)


def test_count_syllables_minimum_one():
    """Every word gets at least 1 syllable (prevents zero-duration words)."""
    from tts.engine import count_syllables
    for word in ["I", "a", "hmm", "nth", "rhythms"]:
        assert count_syllables(word) >= 1, f"'{word}' got 0 syllables"


def test_count_syllables_common_words():
    """Common words should have expected syllable counts."""
    from tts.engine import count_syllables
    cases = {
        "the": 1, "is": 1, "was": 1,
        "because": 2, "today": 2, "about": 2,
        "beautiful": 3, "however": 3,
        "interesting": 4,
    }
    for word, expected in cases.items():
        result = count_syllables(word)
        # Allow ±1 tolerance (syllable counting is approximate)
        assert abs(result - expected) <= 1, (
            f"'{word}': expected ~{expected} syllables, got {result}"
        )


def test_short_words_get_proportional_time():
    """
    With syllable-based timing, short words ('I', 'a') must get
    MORE relative time than character-proportion would give them.
    """
    from tts.engine import estimate_word_segments

    # "I went" — "I" is 1 char but 1 syllable, "went" is 4 chars but 1 syllable
    # syllable-based: equal time each
    # char-based: "went" gets 4x more time than "I"
    segs = estimate_word_segments(None, "I went", fallback_duration=1.0)
    i_dur   = segs[0]["end_time"] - segs[0]["start_time"]
    went_dur = segs[1]["end_time"] - segs[1]["start_time"]

    # With syllable-based timing, ratio should be close to 1:1
    ratio = went_dur / i_dur
    assert ratio < 2.5, (
        f"'went' gets {ratio:.1f}x more time than 'I' — "
        "syllable-based timing should make this closer to 1:1"
    )


def test_multisyllable_words_get_more_time():
    """Multi-syllable words should get proportionally more time."""
    from tts.engine import estimate_word_segments

    # "interesting" (4 syllables) vs "the" (1 syllable)
    segs = estimate_word_segments(None, "the interesting", fallback_duration=2.0)
    the_dur  = segs[0]["end_time"] - segs[0]["start_time"]
    long_dur = segs[1]["end_time"] - segs[1]["start_time"]
    assert long_dur > the_dur * 1.5, (
        f"'interesting' should get >1.5x the time of 'the', "
        f"got {long_dur:.3f}s vs {the_dur:.3f}s"
    )


def test_timing_still_spans_full_duration():
    """Total timing must still span the full audio duration."""
    from tts.engine import estimate_word_segments

    segs = estimate_word_segments(None, "I called my sister out for doing that", fallback_duration=3.5)
    assert abs(segs[-1]["end_time"] - 3.5) < 0.01
    assert segs[0]["start_time"] == 0.0

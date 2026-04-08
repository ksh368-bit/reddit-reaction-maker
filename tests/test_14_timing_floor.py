"""
Test 14: Word timing floor + punctuation pause bonus.

Remaining sync issues after syllable-based fix:
1. Short 1-syllable words in long sentences get < 0.1s → 1-2 frames,
   impossible to perceive the highlight → feels like it's racing ahead
2. TTS pauses naturally at commas/periods, but timing ignores this →
   highlight advances while audio is still pausing

Fix:
- MIN_WORD_DURATION: every word gets at least 0.18s screen time
  (= ~5 frames at 30fps — minimum for the brain to register a highlight)
- Punctuation bonus: words ending in ',', '.', '!', '?' get +0.12s
  (approximates TTS inter-clause pause)
- After applying floor/bonus, rescale so total still equals audio duration

Acceptance criteria:
- No word segment shorter than 0.15s (configurable floor)
- Words ending in sentence-end punctuation get more time than same-syllable
  words without punctuation
- Total timing still spans full duration after adjustments
"""
import pytest


def test_no_word_shorter_than_floor():
    """Every word must get at least 0.15s of screen time."""
    from tts.engine import estimate_word_segments

    # Long sentence where short words would otherwise get < 0.1s
    text = "I am a very good person and I do not deserve this at all"
    segs = estimate_word_segments(None, text, fallback_duration=4.0)

    for s in segs:
        dur = s["end_time"] - s["start_time"]
        assert dur >= 0.15, (
            f"Word '{s['word']}' has duration {dur:.3f}s — below 0.15s floor. "
            "Too short to perceive as a highlight."
        )


def test_punctuation_words_get_longer_duration():
    """Words followed by punctuation must get more time than bare words."""
    from tts.engine import estimate_word_segments

    # "good," has comma → should get more time than "good" without comma
    segs_plain = estimate_word_segments(None, "she was good today", fallback_duration=2.0)
    segs_punct = estimate_word_segments(None, "she was good, today", fallback_duration=2.0)

    # "good" in plain vs "good," in punct — find by index (word 2)
    plain_dur = segs_plain[2]["end_time"] - segs_plain[2]["start_time"]
    punct_dur = segs_punct[2]["end_time"] - segs_punct[2]["start_time"]

    assert punct_dur > plain_dur, (
        f"'good,' ({punct_dur:.3f}s) should get more time than 'good' ({plain_dur:.3f}s). "
        "Punctuation bonus not applied."
    )


def test_total_duration_preserved_after_floor():
    """Total timing must still equal audio duration after floor adjustments."""
    from tts.engine import estimate_word_segments

    text = "I am a very very very good person who does not deserve this"
    segs = estimate_word_segments(None, text, fallback_duration=5.0)

    assert abs(segs[-1]["end_time"] - 5.0) < 0.02, (
        f"Last word ends at {segs[-1]['end_time']:.3f}s, expected 5.0s. "
        "Total duration not preserved after floor adjustment."
    )


def test_monotonic_after_floor():
    """Start times must still be monotonically increasing after adjustments."""
    from tts.engine import estimate_word_segments

    text = "I a the is was and but or so very"
    segs = estimate_word_segments(None, text, fallback_duration=3.0)
    starts = [s["start_time"] for s in segs]
    assert starts == sorted(starts)


def test_floor_applies_even_with_many_short_words():
    """Sentence full of 1-syllable words must still respect the floor."""
    from tts.engine import estimate_word_segments

    # 20 monosyllabic words in 3s = 0.15s each — exactly at floor
    text = " ".join(["the"] * 20)
    segs = estimate_word_segments(None, text, fallback_duration=3.0)

    for s in segs:
        dur = s["end_time"] - s["start_time"]
        assert dur >= 0.14, f"Duration {dur:.3f}s below floor"

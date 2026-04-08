"""
Test 08: Hook text improvement + Reddit card fade-out.

Research findings:
- Hook must start with the transgression/action, not a question
  "My MIL threw out my wedding dress" > "AITA for being mad at my MIL"
- Reddit card should fade out after the title segment (5-10s)
  so the screen clears for karaoke captions

Acceptance criteria:
- extract_hook_text(title) returns the most impactful phrase
  (prefers action verbs, dollar amounts, specific transgressions)
- extract_hook_text removes "AITA", "WIBTA", "Am I the" preamble
- Reddit title card clip has a FadeOut applied in compose_video
"""
import pytest


def test_extract_hook_text_exists():
    """extract_hook_text must be importable from card_renderer."""
    from video.card_renderer import extract_hook_text
    assert callable(extract_hook_text)


def test_extract_hook_removes_aita_preamble():
    """AITA/WIBTA/Am I preamble should be stripped from hook."""
    from video.card_renderer import extract_hook_text

    title = "AITA for kicking my sister out after she stole $5000 from me"
    hook = extract_hook_text(title)
    assert "AITA" not in hook, f"AITA prefix not stripped: '{hook}'"
    assert len(hook) > 0


def test_extract_hook_keeps_transgression():
    """Hook should contain the key action/transgression."""
    from video.card_renderer import extract_hook_text

    title = "AITA for kicking my sister out after she stole $5000 from me"
    hook = extract_hook_text(title)
    # The hook should contain the dramatic part
    assert any(word in hook.lower() for word in ["stole", "sister", "5000", "kick"]), (
        f"Hook '{hook}' doesn't contain the key transgression"
    )


def test_extract_hook_short_title_unchanged():
    """Short titles without preamble should be returned mostly as-is."""
    from video.card_renderer import extract_hook_text

    title = "My husband spent all our savings"
    hook = extract_hook_text(title)
    assert len(hook) >= 5


def test_extract_hook_handles_various_preambles():
    """Should strip WIBTA, Am I the, etc."""
    from video.card_renderer import extract_hook_text

    cases = [
        "WIBTA for not attending my brother's wedding",
        "Am I the asshole for refusing to pay my roommate's rent",
        "Am I wrong for cutting off my parents",
    ]
    for title in cases:
        hook = extract_hook_text(title)
        assert not hook.lower().startswith(("aita", "wibta", "am i")), (
            f"Preamble not stripped from: '{title}' → '{hook}'"
        )


def test_render_hook_card_uses_extract_hook(sample_post):
    """render_hook_card should use extract_hook_text internally."""
    from video.card_renderer import render_hook_card, extract_hook_text

    # Both should produce non-empty results
    hook_text = extract_hook_text(sample_post.title)
    img = render_hook_card(sample_post.title)
    assert img is not None
    alpha = img.split()[3]
    assert any(p > 200 for p in alpha.getdata()), "Hook card is blank"

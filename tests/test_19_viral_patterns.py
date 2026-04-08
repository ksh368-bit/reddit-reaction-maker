"""Tests for 100M+ Shorts viral pattern improvements."""

import os
import sys
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tts.engine import TTSEngine


class TestPreambleStripping:
    """Body preamble lines that burn word budget without story value."""

    def _clean(self, text: str) -> str:
        return TTSEngine.clean_text(text)

    def test_strips_throwaway_line(self):
        text = "Throwaway for obvious reasons.\nSo my sister did something awful."
        assert "Throwaway" not in self._clean(text)
        assert "sister" in self._clean(text)

    def test_strips_throwaway_case_insensitive(self):
        text = "throwaway account because people know me.\nI kicked my boss out."
        assert "throwaway" not in self._clean(text).lower()
        assert "boss" in self._clean(text)

    def test_strips_long_post_sorry_line(self):
        text = "Long post, sorry in advance.\nMy husband forgot our anniversary."
        assert "Long post" not in self._clean(text)
        assert "husband" in self._clean(text)

    def test_strips_edit_section(self):
        text = "I told her she was wrong.\nEDIT: Wow this blew up thanks for the responses."
        result = self._clean(text)
        assert "EDIT:" not in result
        assert "blew up" not in result
        assert "told her" in result

    def test_strips_edit_lowercase(self):
        text = "She left the party.\nedit: for those asking, yes we made up."
        result = self._clean(text)
        assert "edit:" not in result.lower()
        assert "left the party" in result

    def test_strips_update_section(self):
        text = "I fired him on the spot.\nUPDATE: He filed a complaint but HR sided with me."
        result = self._clean(text)
        assert "UPDATE:" not in result
        assert "filed a complaint" not in result
        assert "fired" in result

    def test_strips_for_context_opener(self):
        text = "For context, I am 32F and my mom is 60.\nShe showed up uninvited."
        result = self._clean(text)
        # "For context" opener line should be removed
        assert "For context" not in result
        assert "uninvited" in result

    def test_strips_not_sure_if_right_place(self):
        text = "Not sure if this is the right place but here goes.\nMy coworker stole my lunch."
        result = self._clean(text)
        assert "right place" not in result
        assert "coworker" in result

    def test_keeps_story_when_no_preamble(self):
        text = "My sister invited her ex to my wedding without asking me."
        result = self._clean(text)
        assert "sister" in result
        assert "wedding" in result

    def test_strips_multiple_preamble_patterns(self):
        text = (
            "Throwaway for obvious reasons.\n"
            "Long post, sorry.\n"
            "My dad cut me out of the will."
        )
        result = self._clean(text)
        assert "Throwaway" not in result
        assert "Long post" not in result
        assert "dad" in result

    def test_edit_section_at_end_fully_removed(self):
        """Everything after EDIT: should be gone."""
        text = "She slapped me in front of everyone. EDIT: A lot of you are asking about the context."
        result = self._clean(text)
        assert "slapped" in result
        assert "asking about" not in result


class TestCommentPacing:
    """Comments should be short and punchy — max ~80 chars, top 2 only."""

    def test_config_top_comments_max_2(self):
        import tomllib
        with open("config.toml", "rb") as f:
            cfg = tomllib.load(f)
        assert cfg["reddit"]["top_comments"] <= 2, \
            f"top_comments should be ≤2, got {cfg['reddit']['top_comments']}"

    def test_config_max_comment_length_max_80(self):
        import tomllib
        with open("config.toml", "rb") as f:
            cfg = tomllib.load(f)
        assert cfg["reddit"]["max_comment_length"] <= 80, \
            f"max_comment_length should be ≤80, got {cfg['reddit']['max_comment_length']}"

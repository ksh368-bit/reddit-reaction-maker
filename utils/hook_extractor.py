"""
hook_extractor.py — 바이럴 훅 추출 유틸리티.

- score_sentence(s)             → 충격 점수 (높을수록 바이럴 가능성 ↑)
- extract_money_quote(body)     → 가장 충격적인 문장 | None
- extract_conflict_core(body)   → 갈등 절정까지 읽은 텍스트
"""
from __future__ import annotations

import re

# 충격 키워드 패턴
_SHOCK = re.compile(
    r'\b(never|always|worst|lied|cheated|kicked|fired|stole|hit|left|'
    r'pregnant|divorce|police|hospital|threatened|affair|assault|betrayed|'
    r'disowned|blocked|screamed|cried|walked\s+out)\b',
    re.I,
)


def score_sentence(s: str) -> int:
    """문장의 충격/바이럴 점수를 반환 (높을수록 우선 선택)."""
    pts  = s.count('!') * 3
    pts += len(_SHOCK.findall(s)) * 4
    pts += len(re.findall(r'\$[\d,]+', s)) * 3           # 금액 표현
    pts += len(re.findall(r'\b[A-Z]{2,}\b', s)) * 2      # 대문자 강조
    pts += len(re.findall(r'\b(he|she|they)\b', s, re.I))  # 3인칭 갈등
    return pts


def extract_money_quote(body: str, min_score: int = 4) -> str | None:
    """
    body에서 가장 충격적인 문장을 반환.

    - min_score 미달이면 None 반환 → 호출자는 title 기반 훅으로 폴백.
    - 20 < len(sentence) < 120 범위 문장만 고려 (너무 짧거나 긴 문장 제외).
    """
    if not body or len(body.strip()) < 30:
        return None

    sentences = re.split(r'(?<=[.!?])\s+', body.strip())
    candidates = [s.strip() for s in sentences if 20 < len(s.strip()) < 120]
    if not candidates:
        return None

    best = max(candidates, key=score_sentence)
    if score_sentence(best) < min_score:
        return None

    # 첫 글자 대문자
    return best[0].upper() + best[1:]


def extract_conflict_core(body: str, max_chars: int = 500) -> str:
    """
    본문에서 갈등 절정 문장 포함 블록을 반환.

    - 절정 문장(최고 점수) 이후 +1 문장까지 포함 후 컷
    - 절정 점수 < 3이면 일반 문장 경계 truncation (폴백)
    - 결과가 max_chars 초과하면 _truncate_at_sentence() 적용
    """
    if not body:
        return ""

    sentences = re.split(r'(?<=[.!?])\s+', body.strip())
    sentences = [s for s in sentences if s.strip()]
    if not sentences:
        return _truncate_at_sentence(body, max_chars)

    scores = [score_sentence(s) for s in sentences]
    peak_idx = max(range(len(scores)), key=lambda i: scores[i])

    if scores[peak_idx] < 3:
        # 갈등 없음 → 일반 truncation
        return _truncate_at_sentence(body, max_chars)

    # 절정 +1 문장까지 포함 (독자가 충격을 소화할 여유)
    end_idx = min(peak_idx + 1, len(sentences) - 1)
    result = ' '.join(sentences[:end_idx + 1])

    if len(result) <= max_chars:
        return result
    return _truncate_at_sentence(result, max_chars)


def _truncate_at_sentence(text: str, max_chars: int) -> str:
    """max_chars 이내에서 마지막 완전한 문장 끝에서 컷. 없으면 단어 경계."""
    if len(text) <= max_chars:
        return text
    window = text[:max_chars]
    m = re.search(r'[.!?](?=[^.!?]*$)', window)
    if m and m.start() > max_chars // 2:
        return window[:m.start() + 1].strip()
    return window.rsplit(' ', 1)[0]

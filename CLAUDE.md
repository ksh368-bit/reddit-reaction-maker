# Development Policy

## TDD (Test-Driven Development)

모든 기능 개발 및 수정 시 TDD를 따른다:

1. **테스트 먼저** — 구현 전에 실패하는 테스트를 작성한다
2. **최소 구현** — 테스트를 통과할 최소한의 코드만 작성한다
3. **리팩터** — 테스트가 통과한 후 코드를 정리한다

### 규칙
- 새 기능 → `tests/test_NN_feature.py` 파일에 테스트 먼저 작성
- 버그 수정 → 버그를 재현하는 테스트를 먼저 작성
- 테스트 실행: `path/to/venv/bin/python3 -m pytest tests/ -q`
- 모든 기존 테스트가 통과한 상태에서 커밋

## 오디오/텍스트 싱크 원칙

**`TTSEngine.prepare_tts_text(text, max_chars)`** 가 TTS가 실제로 읽는 텍스트의 유일한 소스다.

- `word_segments`를 만드는 코드는 반드시 `prepare_tts_text()`를 통해 얻은 텍스트를 사용해야 한다
- raw text / `clean_text()` 결과를 그대로 `estimate_word_segments`에 넘기면 안 된다
- `segment['text']`도 `prepare_tts_text()` 결과여야 화면 텍스트 = 음성 텍스트가 보장된다

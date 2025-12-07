from namel3ss.ai.providers.gemini import GeminiProvider
from namel3ss.errors import Namel3ssError


def _mock_response(text: str):
    return {
        "candidates": [
            {
                "content": {"parts": [{"text": text}]},
                "finish_reason": "stop",
            }
        ]
    }


def test_gemini_generate_plain():
    provider = GeminiProvider("gemini", api_key="test", default_model="gemini-pro", http_client=lambda u, b, h: _mock_response("hi"))
    resp = provider.generate([{"role": "user", "content": "Hello"}])
    assert resp.text == "hi"
    assert resp.raw is not None


def test_gemini_generate_json_mode_parses():
    provider = GeminiProvider(
        "gemini", api_key="test", default_model="gemini-pro", http_client=lambda u, b, h: _mock_response('{"a":1}')
    )
    resp = provider.generate([{"role": "user", "content": "Hi"}], json_mode=True)
    assert resp.json == {"a": 1}


def test_gemini_generate_invalid_json_raises():
    provider = GeminiProvider(
        "gemini", api_key="test", default_model="gemini-pro", http_client=lambda u, b, h: _mock_response("{bad")
    )
    try:
        provider.generate([{"role": "user", "content": "Hi"}], json_mode=True)
        assert False, "expected error"
    except Namel3ssError:
        pass


def test_gemini_stream_plain():
    provider = GeminiProvider(
        "gemini",
        api_key="test",
        default_model="gemini-pro",
        http_stream=lambda u, b, h: iter([_mock_response("chunk1"), _mock_response("chunk2")]),
    )
    chunks = list(provider.stream([{"role": "user", "content": "Hi"}]))
    assert len(chunks) == 2
    assert chunks[0].delta == "chunk1"
    assert chunks[1].delta == "chunk2"


def test_gemini_stream_json_mode_parses():
    provider = GeminiProvider(
        "gemini",
        api_key="test",
        default_model="gemini-pro",
        http_stream=lambda u, b, h: iter([_mock_response('{"step":1}'), _mock_response('{"step":2}')]),
    )
    chunks = list(provider.stream([{"role": "user", "content": "Hi"}], json_mode=True))
    assert chunks[0].json == {"step": 1}
    assert chunks[1].json == {"step": 2}


def test_gemini_missing_api_key_errors():
    provider = GeminiProvider("gemini", api_key="", default_model="gemini-pro", http_client=lambda u, b, h: {})
    try:
        provider.generate([{"role": "user", "content": "Hello"}])
        assert False, "expected error"
    except Namel3ssError:
        pass

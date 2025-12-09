from namel3ss.memory.summarisation import ConversationSummaryConfig, summarise_conversation


def test_summarise_conversation_invokes_summariser_when_enabled():
    called = {"count": 0, "transcript": ""}

    def _summariser(transcript: str, cfg: ConversationSummaryConfig) -> str:
        called["count"] += 1
        called["transcript"] = transcript
        return "summary-text"

    messages = [{"role": "user", "content": f"msg-{i}"} for i in range(6)]
    cfg = ConversationSummaryConfig(max_messages_before_summary=3, target_summary_length=1, enabled=True)
    result = summarise_conversation(messages, config=cfg, summariser=_summariser, recent_preserve=2)
    assert called["count"] == 1
    assert called["transcript"].startswith("user: msg-0")
    assert result[0]["content"] == "summary-text"
    assert len(result) == 3  # summary + last 2 preserved


def test_summarise_conversation_skips_when_disabled():
    called = {"count": 0}

    def _summariser(transcript: str, cfg: ConversationSummaryConfig) -> str:  # pragma: no cover - should not run
        called["count"] += 1
        return transcript

    messages = [{"role": "user", "content": "hello"}, {"role": "assistant", "content": "hi"}]
    cfg = ConversationSummaryConfig(max_messages_before_summary=1, enabled=False)
    result = summarise_conversation(messages, config=cfg, summariser=_summariser)
    assert called["count"] == 0
    assert result == messages

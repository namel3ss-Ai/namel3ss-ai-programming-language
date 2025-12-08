from textwrap import dedent

import pytest

from namel3ss import parser
from namel3ss.ir import ast_to_ir
from namel3ss.ir import IRFlowStep
from namel3ss.errors import IRError


def test_parse_ai_streaming_true():
    module = parser.parse_source(
        dedent(
            """
            ai is "support_bot":
              model is "gpt-4.1-mini"

            model "gpt-4.1-mini":
              provider "openai:gpt-4.1-mini"

            flow is "chat_turn":
              step is "answer":
                kind is "ai"
                target is "support_bot"
                streaming is true
            """
        )
    )
    ir = ast_to_ir(module)
    flow = ir.flows["chat_turn"]
    step: IRFlowStep = flow.steps[0]
    assert step.params.get("streaming") is True
    assert step.streaming is True


def test_parse_ai_streaming_default_false():
    module = parser.parse_source(
        dedent(
            """
            ai is "support_bot":
              model is "gpt-4.1-mini"

            model "gpt-4.1-mini":
              provider "openai:gpt-4.1-mini"

            flow is "chat_turn":
              step is "answer":
                kind is "ai"
                target is "support_bot"
            """
        )
    )
    ir = ast_to_ir(module)
    flow = ir.flows["chat_turn"]
    step: IRFlowStep = flow.steps[0]
    assert step.params.get("streaming") is None or step.params.get("streaming") is False
    assert step.streaming is False


def test_parse_ai_streaming_metadata_fields():
    module = parser.parse_source(
        dedent(
            """
            ai is "support_bot":
              model is "gpt-4.1-mini"

            model "gpt-4.1-mini":
              provider "openai:gpt-4.1-mini"

            flow is "chat_turn":
              step is "answer":
                kind is "ai"
                target is "support_bot"
                streaming is true
                stream_channel is "chat"
                stream_role is "assistant"
                stream_label is "Support Bot"
                stream_mode is "tokens"
            """
        )
    )
    ir = ast_to_ir(module)
    flow = ir.flows["chat_turn"]
    step: IRFlowStep = flow.steps[0]
    assert step.streaming is True
    assert step.stream_channel == "chat"
    assert step.stream_role == "assistant"
    assert step.stream_label == "Support Bot"
    assert step.stream_mode == "tokens"


def test_invalid_streaming_literal_raises():
    with pytest.raises(Exception):
        parser.parse_source(
            dedent(
                """
                ai is "support_bot":
                  model is "gpt-4.1-mini"

                model "gpt-4.1-mini":
                  provider "openai:gpt-4.1-mini"

                flow is "chat_turn":
                  step is "answer":
                    kind is "ai"
                    target is "support_bot"
                    streaming is "yes"
                """
            )
        )


def test_invalid_stream_mode_diagnostic():
    with pytest.raises(Exception) as excinfo:
        parser.parse_source(
            dedent(
                """
                ai is "support_bot":
                  model is "gpt-4.1-mini"

                model "gpt-4.1-mini":
                  provider "openai:gpt-4.1-mini"

                flow is "chat_turn":
                  step is "answer":
                    kind is "ai"
                    target is "support_bot"
                    streaming is true
                    stream_mode is "chars"
                """
            )
        )
    assert "N3L-995" in str(excinfo.value)

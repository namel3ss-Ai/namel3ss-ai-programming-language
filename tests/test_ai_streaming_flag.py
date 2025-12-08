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

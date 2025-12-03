from namel3ss.lexer import Lexer


def test_lex_use_line():
    tokens = Lexer('use "common.ai"\n').tokenize()
    assert [t.type for t in tokens[:3]] == ["KEYWORD", "STRING", "NEWLINE"]
    assert tokens[0].value == "use"
    assert tokens[1].value == "common.ai"
    assert tokens[-1].type == "EOF"


def test_lex_app_block_with_indentation():
    source = (
        'app "x":\n'
        '  description "Demo"\n'
        '  entry_page "home"\n'
    )
    tokens = Lexer(source).tokenize()
    types = [t.type for t in tokens]
    assert "INDENT" in types
    assert "DEDENT" in types
    assert types[:4] == ["KEYWORD", "STRING", "COLON", "NEWLINE"]
    # Ensure nested fields are recognized
    assert any(t.value == "description" for t in tokens)
    assert any(t.value == "entry_page" for t in tokens)


def test_lex_model_provider():
    source = (
        'model "default":\n'
        '  provider "openai:gpt-4.1-mini"\n'
    )
    tokens = Lexer(source).tokenize()
    values = [t.value for t in tokens if t.value]
    assert "model" in values
    assert "provider" in values
    assert "openai:gpt-4.1-mini" in values


def test_lex_agent_and_memory_keywords():
    source = (
        'agent "helper":\n'
        '  goal "Assist users"\n'
        '  personality "friendly"\n'
        'memory "short_term":\n'
        '  type "conversation"\n'
    )
    tokens = Lexer(source).tokenize()
    values = [t.value for t in tokens if t.value]
    for expected in ["agent", "goal", "personality", "memory", "type"]:
        assert expected in values

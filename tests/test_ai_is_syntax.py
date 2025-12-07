from namel3ss import parser, ast_nodes


def test_ai_is_syntax_parses():
    mod = parser.parse_source(
        '''
ai is "support_bot":
  model is "gpt-4.1-mini"
  system is "You are helpful"
'''
    )
    ai_decl = next(decl for decl in mod.declarations if isinstance(decl, ast_nodes.AICallDecl))
    assert ai_decl.name == "support_bot"
    assert ai_decl.model_name == "gpt-4.1-mini"
    assert ai_decl.system_prompt == "You are helpful"


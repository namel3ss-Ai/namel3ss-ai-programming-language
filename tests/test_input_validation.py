from textwrap import dedent

from namel3ss import parser
from namel3ss.ir import ast_to_ir
from namel3ss.ui.manifest import build_ui_manifest
from namel3ss.ui.runtime import validate_inputs


def test_parse_input_validation_manifest():
    module = parser.parse_source(
        dedent(
            """
            page is "register" at "/":
              section is "form":
                input is "email":
                  bind is state.email
                  required is true
                  min_length is 5
                  max_length is 200
                  pattern is ".+@.+\\\\..+"
                  message is "Please enter a valid email address."
            """
        )
    )
    ir = ast_to_ir(module)
    manifest = build_ui_manifest(ir)
    page = manifest["pages"][0]
    input_el = page["layout"][0]["layout"][0]
    validation = input_el["validation"]
    assert validation["required"] is True
    assert validation["minLength"] == 5
    assert validation["maxLength"] == 200
    assert validation["pattern"].startswith(".+@")
    assert "valid email" in validation["message"]


def test_backend_validation_required_and_pattern():
    module = parser.parse_source(
        dedent(
            """
            page is "register" at "/":
              section is "form":
                input is "email":
                  bind is state.email
                  required is true
                  pattern is ".+@.+\\\\..+"
                  message is "Please enter a valid email address."
            """
        )
    )
    ir = ast_to_ir(module)
    manifest = build_ui_manifest(ir)
    page_manifest = manifest["pages"][0]

    # Missing value should fail
    ok, errors = validate_inputs(page_manifest, {"email": ""})
    assert not ok
    assert errors

    # Invalid pattern should fail
    ok, errors = validate_inputs(page_manifest, {"email": "invalid"})
    assert not ok

    # Valid value should pass
    ok, errors = validate_inputs(page_manifest, {"email": "user@example.com"})
    assert ok
    assert not errors

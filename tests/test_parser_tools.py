from textwrap import dedent

import namel3ss.ast_nodes as ast_nodes
from namel3ss.parser import parse_source


def test_parse_graphql_tool():
    src = dedent(
        '''
    tool is "product_graphql":
      kind is "graphql"
      url is "https://api.example.com/graphql"
      query_template is "query Product($id: ID!) { product(id: $id) { id name } }"
      variables:
        id is input.product_id
    '''
    )
    module = parse_source(src)
    tool = next(d for d in module.declarations if isinstance(d, ast_nodes.ToolDeclaration))
    assert tool.kind == "graphql"
    assert tool.query_template is not None
    assert "id" in tool.variables


def test_parse_oauth_auth_block():
    src = dedent(
        '''
    tool is "crm_api":
      kind is "http"
      method is "GET"
      url is "https://auth.example.com"
      auth:
        kind is "oauth2_client_credentials"
        token_url is "https://auth.example.com/token"
        client_id is secret.CRM_ID
        client_secret is secret.CRM_SECRET
        scopes are ["read", "write"]
        cache is "shared"
    '''
    )
    module = parse_source(src)
    tool = next(d for d in module.declarations if isinstance(d, ast_nodes.ToolDeclaration))
    assert tool.auth
    assert tool.auth.kind == "oauth2_client_credentials"
    assert tool.auth.token_url
    assert tool.auth.client_id
    assert tool.auth.scopes == ["read", "write"]


def test_parse_tool_evaluation():
    src = dedent(
        '''
    tool evaluation is "weather_eval":
      tool is "weather_api"
      dataset_frame is "cases"
      input_mapping:
        city is "city_name"
      expected:
        status_column is "expected_status"
        body_column is "expected_body"
      metrics:
        - "success_rate"
    '''
    )
    module = parse_source(src)
    decl = next(d for d in module.declarations if isinstance(d, ast_nodes.ToolEvaluationDecl))
    assert decl.tool == "weather_api"
    assert decl.dataset_frame == "cases"
    assert decl.input_mapping["city"] == "city_name"
    assert decl.expected.body_column == "expected_body"
    assert decl.metrics == ["success_rate"]

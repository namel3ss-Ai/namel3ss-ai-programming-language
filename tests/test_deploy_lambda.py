from namel3ss.deploy.aws_lambda import lambda_handler


def test_lambda_handler_health():
    event = {"httpMethod": "GET", "path": "/health", "headers": {}, "body": "", "isBase64Encoded": False}
    result = lambda_handler(event, None)
    assert result["statusCode"] == 200
    assert "ok" in result["body"]

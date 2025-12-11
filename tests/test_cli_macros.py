from namel3ss.cli import main


def test_cli_macro_migrate(capsys):
    main(["macro", "migrate", "--macro", "crud_ui", "--from", "1.0", "--to", "1.1"])
    out = capsys.readouterr().out
    assert "crud_ui" in out
    assert "1.1" in out

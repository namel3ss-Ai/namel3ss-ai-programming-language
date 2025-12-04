from namel3ss.lang.spec.registry import get_contract, all_contracts


def test_contracts_exist_for_core_blocks():
    kinds = {"app", "page", "model", "ai", "agent", "flow", "memory", "plugin", "section", "component"}
    for kind in kinds:
        assert get_contract(kind) is not None
    registered = {c.kind for c in all_contracts()}
    assert kinds.issubset(registered)


def test_page_contract_fields():
    contract = get_contract("page")
    assert contract is not None
    required = {f.name for f in contract.required_fields}
    optional = {f.name for f in contract.optional_fields}
    assert "route" in required
    assert "title" in optional

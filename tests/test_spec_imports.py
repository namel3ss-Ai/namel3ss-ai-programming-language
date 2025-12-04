def test_spec_public_imports():
    from namel3ss.lang.spec import BlockContract, FieldSpec, get_contract, all_contracts, validate_ir_module

    assert BlockContract is not None
    assert FieldSpec is not None
    assert callable(get_contract)
    assert callable(all_contracts)
    assert callable(validate_ir_module)

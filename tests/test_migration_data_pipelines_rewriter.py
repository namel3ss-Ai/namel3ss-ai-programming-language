from namel3ss.migration.data_pipelines import rewrite_source


def test_rewrite_all_from_where_to_pipeline():
    source = (
        'flow is "f":\n'
        '  step is "s":\n'
        '    let filtered be all row from sales_data where row.country is "BE"\n'
    )
    migrated, result = rewrite_source(source)
    assert "keep rows where row.country is \"BE\"" in migrated
    assert "let filtered be sales_data:" in migrated
    assert result.rewrites == 1
    assert result.changed


def test_rewrite_all_where_without_from():
    source = (
        'flow is "f":\n'
        '  step is "s":\n'
        "    all items where item > 0\n"
    )
    migrated, result = rewrite_source(source)
    assert "keep rows where row > 0" in migrated
    assert "let filtered_rows be items:" in migrated
    assert result.rewrites == 1

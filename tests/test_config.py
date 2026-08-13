from saletool.config import load_criteria


def test_load_criteria_from_example_yaml():
    criteria = load_criteria("examples/search_criteria.example.yaml")

    assert "Software" in criteria.industries
    assert criteria.max_companies == 20
    assert criteria.max_contacts_per_company == 5
    assert "CEO" in criteria.target_titles


def test_load_criteria_missing_file(tmp_path):
    import pytest

    with pytest.raises(FileNotFoundError):
        load_criteria(tmp_path / "does_not_exist.yaml")


def test_load_criteria_defaults(tmp_path):
    config_file = tmp_path / "minimal.yaml"
    config_file.write_text("keywords: [saas]\n", encoding="utf-8")

    criteria = load_criteria(config_file)

    assert criteria.keywords == ["saas"]
    assert criteria.max_companies == 20  # default
    assert criteria.seniority_levels  # default seniority list is non-empty

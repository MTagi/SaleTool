import pytest

from saletool.identity import lookup_company_match, resolve_message_target
from saletool.models import (
    Company,
    CompanyMatch,
    CompanyResult,
    Contact,
    MessageTarget,
    SearchCriteria,
    SearchRunDetail,
)


def make_run(results):
    return SearchRunDetail(
        id="run",
        username="alice",
        created_at="now",
        provider="apollo",
        criteria=SearchCriteria(),
        total_companies=len(results),
        total_contacts=sum(len(r.contacts) for r in results),
        results=results,
    )


def test_legacy_snapshot_ids_survive_reloads_and_distinguish_contacts():
    raw = {"company": {"name": "Acme"}, "contacts": [{"full_name": "John"}, {"full_name": "John"}]}
    first = CompanyResult.model_validate(raw)
    second = CompanyResult.model_validate(raw)
    assert first.company.id == second.company.id
    assert [c.id for c in first.contacts] == [c.id for c in second.contacts]
    assert first.contacts[0].id != first.contacts[1].id


def test_ids_select_the_right_contact_in_companies_with_the_same_name():
    run = make_run(
        [
            CompanyResult(
                company=Company(name="Acme", domain=domain),
                contacts=[
                    Contact(full_name="John", email=f"john.one@{domain}"),
                    Contact(full_name="John", email=f"john.two@{domain}"),
                ],
            )
            for domain in ("one.example", "two.example")
        ]
    )
    wanted = run.results[1]
    target = MessageTarget(
        company_name="Acme",
        contact_name="John",
        company_id=wanted.company.id,
        contact_id=wanted.contacts[1].id,
    )
    result, contact = resolve_message_target(run, target)
    assert result is wanted
    assert contact.email == "john.two@two.example"
    target.contact_id = run.results[0].contacts[1].id
    assert resolve_message_target(run, target)[1] is None


@pytest.mark.parametrize("duplicate_company", [True, False])
def test_names_alone_must_not_select_ambiguous_recipients(duplicate_company):
    result = CompanyResult(company=Company(name="Acme"), contacts=[Contact(full_name="John")])
    if duplicate_company:
        results = [result, CompanyResult(company=Company(name="Acme", domain="other.example"))]
    else:
        result.contacts.append(Contact(full_name="John"))
        results = [result]
    with pytest.raises(ValueError, match="ambiguous"):
        resolve_message_target(
            make_run(results), MessageTarget(company_name="Acme", contact_name="John")
        )


def test_matching_context_does_not_cross_company_identity():
    result = CompanyResult(company=Company(name="Acme", domain="one.example"))
    wrong = CompanyMatch(company_name="Acme", domain="two.example")
    right = CompanyMatch(company_name="Acme", domain="one.example", company_id=result.company.id)
    assert lookup_company_match([wrong], result) is None
    assert lookup_company_match([wrong, right], result) is right

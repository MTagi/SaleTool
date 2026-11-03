"""Read saved workflow results without starting any external API calls."""

from saletool.db.factory import (
    get_enrich_job_repository,
    get_match_job_repository,
    get_message_job_repository,
)
from saletool.enrichment.discovery import normalize_domain
from saletool.models import SearchRunDetail


def same_company(name: str, domain: str | None, other_name: str, other_domain: str | None) -> bool:
    """Known conflicting domains must never match just because names are equal."""
    left = normalize_domain(domain or "")
    right = normalize_domain(other_domain or "")
    if left and right:
        return left == right
    return bool(name.strip()) and name.strip().casefold() == other_name.strip().casefold()


def read_workflow_history(run: SearchRunDetail) -> dict:
    companies = [item.company for item in run.results]

    def belongs(item) -> bool:
        return any(same_company(c.name, c.domain, item.company_name, item.domain) for c in companies)

    enrich_jobs = []
    # Old jobs and manually pasted companies have no run_id. Match only their
    # relevant companies and keep this distinction visible in the response.
    for job in get_enrich_job_repository().list_for_run(run.username, run.id, include_unlinked=True):
        targets = [target for target in job.targets if belongs(target)]
        results = [result for result in job.results if belongs(result)]
        if job.run_id != run.id and not targets and not results:
            continue
        payload = job.model_dump(mode="json")
        payload["targets"] = [target.model_dump(mode="json") for target in targets]
        payload["results"] = [result.model_dump(mode="json") for result in results]
        enrich_jobs.append(payload)

    # One latest saved result per search row. Older versions remain available
    # in enrich_jobs, including empty results and failed/partial runs.
    enrichments = []
    for company in companies:
        latest = next(
            (
                result
                for job in enrich_jobs
                for result in job["results"]
                if same_company(company.name, company.domain, result["company_name"], result["domain"])
            ),
            None,
        )
        enrichments.append(latest)

    return {
        "run": run.model_dump(mode="json"),
        "enrichments": enrichments,
        "enrich_jobs": enrich_jobs,
        "match_jobs": [
            job.model_dump(mode="json")
            for job in get_match_job_repository().list_for_run(run.username, run.id)
        ],
        "message_jobs": [
            job.model_dump(mode="json")
            for job in get_message_job_repository().list_for_run(run.username, run.id)
        ],
    }

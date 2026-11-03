"""Storage interfaces for accounts and search history, independent of a specific database.

The API/CLI only use these interfaces. Switching from SQLite to MongoDB (or any
other database) only requires another implementation, not changes to routes or
authentication/search logic.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Generic, TypeVar

from saletool.models import (
    AppSettings,
    CompanyResult,
    EnrichJobDetail,
    EnrichJobSummary,
    MatchJobDetail,
    MatchJobSummary,
    MessageJobDetail,
    MessageJobSummary,
    SearchCriteria,
    SearchRunDetail,
    SearchRunSummary,
    Service,
    ServiceInput,
)


class UserRepository(ABC):
    @abstractmethod
    def create_user(self, username: str, password_hash: str) -> None:
        """Create an account. Raise ValueError if the username already exists."""

    @abstractmethod
    def get_password_hash(self, username: str) -> str | None:
        """Return the saved password hash, or None if the user is not found."""

    @abstractmethod
    def update_password_hash(self, username: str, password_hash: str) -> None:
        """Update the password hash for an existing user. Raise ValueError if not found."""


class SearchRunRepository(ABC):
    @abstractmethod
    def save_run(
        self,
        username: str,
        provider: str,
        criteria: SearchCriteria,
        results: list[CompanyResult],
    ) -> SearchRunSummary:
        """Save a search run and return its summary (including generated id and created_at)."""

    @abstractmethod
    def list_runs(self, username: str, limit: int = 20) -> list[SearchRunSummary]:
        """List the user's recent search runs, newest first."""

    @abstractmethod
    def get_run(self, username: str, run_id: str) -> SearchRunDetail | None:
        """Full details (including results) for a search run. Return None if it does not
        exist or does not belong to this user (users cannot view another's history)."""

    @abstractmethod
    def get_latest_run(self, username: str) -> SearchRunDetail | None:
        """The user's latest search run, used for downloads when run_id is omitted."""

    @abstractmethod
    def delete_run(self, username: str, run_id: str) -> bool:
        """Delete one of the user's search runs. Return False if missing or not owned by the user."""

class SettingsRepository(ABC):
    """System-wide configuration (one record), not per-user.

    API keys are stored encrypted; see saletool/crypto.py.
    """

    @abstractmethod
    def get_settings(self) -> AppSettings:
        """Return the current configuration (including decrypted API keys), or defaults if never saved."""

    @abstractmethod
    def save_settings(self, settings: AppSettings, updated_by: str) -> AppSettings:
        """Replace the configuration and return the saved version (including updated_at/updated_by)."""


class ServiceRepository(ABC):
    """The company's service catalog — system-wide, not per-user.

    The sales team shares one service list, so it is not separated by user;
    `updated_by` records who last changed it.
    """

    @abstractmethod
    def list_services(self, include_inactive: bool = True) -> list[Service]:
        """Return the full catalog, sorted by name."""

    @abstractmethod
    def get_service(self, service_id: str) -> Service | None:
        """Get one service by ID. Return None if it does not exist."""

    @abstractmethod
    def create_service(self, payload: ServiceInput, updated_by: str) -> Service:
        """Add a service and return the saved version (including generated ID and timestamp)."""

    @abstractmethod
    def update_service(self, service_id: str, payload: ServiceInput, updated_by: str) -> Service:
        """Replace a service. Raise ValueError if the ID does not exist."""

    @abstractmethod
    def delete_service(self, service_id: str) -> bool:
        """Delete a service. Return False if the ID does not exist."""


TSummary = TypeVar("TSummary")
TDetail = TypeVar("TDetail")


class JobRepository(ABC, Generic[TSummary, TDetail]):
    """Persist the state of one type of background job.

    The three job types (enrichment, matching, messaging) share a lifecycle —
    create, update progress, retrieve, and list by user — so they use this
    interface and differ only in data type. The subclasses provide distinct names
    for dependency declarations.
    """

    @abstractmethod
    def create_job(self, job: TDetail) -> None:
        """Create a job record."""

    @abstractmethod
    def update_job(self, job: TDetail) -> None:
        """Replace a job's state (used to update progress)."""

    @abstractmethod
    def fail_active_jobs(self, reason: str, finished_at: str) -> int:
        """Close pending/running jobs after restart while preserving saved results."""

    @abstractmethod
    def get_job(self, username: str, job_id: str) -> TDetail | None:
        """Get job details. Return None if missing or not owned by this user."""

    @abstractmethod
    def list_jobs(self, username: str, limit: int = 20) -> list[TSummary]:
        """List the user's recent jobs, newest first."""

    @abstractmethod
    def list_for_run(
        self, username: str, run_id: str, include_unlinked: bool = False
    ) -> list[TDetail]:
        """All saved jobs for an owned search, newest first; optionally include legacy jobs."""

    @abstractmethod
    def delete_for_run(self, username: str, run_id: str) -> None:
        """Delete all jobs for a search run; only matching run_id values, not legacy jobs (run_id null)."""

class EnrichJobRepository(JobRepository[EnrichJobSummary, EnrichJobDetail]):
    """Enrichment job: read company websites to collect additional information."""


class MatchJobRepository(JobRepository[MatchJobSummary, MatchJobDetail]):
    """Matching job: score and rank companies against the service catalog."""


class MessageJobRepository(JobRepository[MessageJobSummary, MessageJobDetail]):
    """Messaging job: write a message for each contact."""

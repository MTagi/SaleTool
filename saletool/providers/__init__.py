from saletool.providers.base import CompanyContactProvider

__all__ = ["CompanyContactProvider", "get_provider"]


def get_provider(name: str, **kwargs) -> CompanyContactProvider:
    """Factory for creating a provider by name.

    Apollo is currently the only provider. The factory and `CompanyContactProvider`
    interface remain so another provider can be added later (People Data Labs,
    Coresignal, manual CSV import, etc.) without changing routes or the pipeline.
    See git history for the removed `mock` and `csv_import` providers.
    """
    if name == "apollo":
        from saletool.providers.apollo import ApolloProvider

        return ApolloProvider(**kwargs)
    raise ValueError(f"Unsupported provider: {name}")

from saletool.providers.base import CompanyContactProvider
from saletool.providers.mock import MockProvider

__all__ = ["CompanyContactProvider", "MockProvider", "get_provider"]


def get_provider(name: str, **kwargs) -> CompanyContactProvider:
    """Factory: khởi tạo provider theo tên ('apollo', 'mock', ...)."""

    if name == "mock":
        return MockProvider()
    if name == "apollo":
        from saletool.providers.apollo import ApolloProvider

        return ApolloProvider(**kwargs)
    raise ValueError(f"Provider không được hỗ trợ: {name}")

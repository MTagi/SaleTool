from saletool.providers.base import CompanyContactProvider

__all__ = ["CompanyContactProvider", "get_provider"]


def get_provider(name: str, **kwargs) -> CompanyContactProvider:
    """Factory khởi tạo provider theo tên.

    Hiện chỉ có Apollo. Factory và interface `CompanyContactProvider` được giữ
    lại để thêm nhà cung cấp khác sau này (People Data Labs, Coresignal, import
    CSV thủ công…) mà không phải sửa route hay pipeline — xem lịch sử git cho
    hai provider `mock` và `csv_import` đã gỡ.
    """
    if name == "apollo":
        from saletool.providers.apollo import ApolloProvider

        return ApolloProvider(**kwargs)
    raise ValueError(f"Provider không được hỗ trợ: {name}")

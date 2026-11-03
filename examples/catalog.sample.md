# Catalog mẫu cho demo ABIM

File dữ liệu: [catalog.sample.json](catalog.sample.json).

Đây là mô tả dịch vụ giả định để thử Matching và Messages, không phải xác nhận năng lực hoặc cam kết thương mại của ABIM. Rà soát lại trước khi dùng để tiếp cận khách hàng thật.

| Dịch vụ | Tình huống phù hợp | Người liên hệ gợi ý |
|---|---|---|
| AI VMS — Restricted-area monitoring | Nhà máy/kho có vùng hạn chế, giám sát camera thủ công | Operations Director, Head of Security, IT Manager |
| AI Safety — PPE monitoring | Nhà máy/công trường có quy định mũ và áo bảo hộ | EHS Manager, Plant Manager, Operations Director |
| ERP — Manufacturing operations | Đơn hàng, kho và kế hoạch sản xuất nằm ở nhiều file/phần mềm | COO, CFO, Plant Manager, IT Manager |
| Data Platform — Operations dashboard | Báo cáo liên phòng ban tổng hợp thủ công từ nhiều hệ thống | COO, CFO, Head of Data, IT Director |
| WMS — Warehouse traceability | Nhiều vị trí kho, cần theo dõi lô và đối chiếu tồn kho | Warehouse Manager, Logistics Director, COO |

## Nhập trên giao diện

1. Mở **Catalog** và tạo dịch vụ mới.
2. Sao chép các trường tương ứng của một phần tử JSON: `name`, `category`, `description`, `value_proposition`, `target_industries`, `target_company_size`, `keywords`.
3. Với `target_industries` và `keywords`, nhập các giá trị cách nhau bằng dấu phẩy, không cần dấu ngoặc JSON.
4. Bật **Offered** (`active: true`) rồi lưu. Lặp lại với những dịch vụ muốn demo.

UI hiện chưa có chức năng import file Catalog. Mỗi phần tử JSON cũng là một payload hợp lệ cho `POST /api/catalog` khi dùng API đã xác thực; không gửi cả mảng trong một request.

## Thử Matching và Messages

- Dùng search theo `test_abim_vms.yaml`, chọn AI VMS và AI Safety để so sánh nhu cầu giám sát với nhu cầu an toàn.
- Thêm ERP, Data Platform và WMS để quan sát cách hệ thống phân biệt dịch vụ phù hợp với từng công ty.
- Objective gợi ý: “Ưu tiên doanh nghiệp có dấu hiệu vận hành nhà máy hoặc kho. Chỉ viện dẫn dữ liệu đã có; không suy đoán rằng khách hàng đã lắp camera hoặc đang dùng ERP nếu chưa có bằng chứng.”
- Trong Messages, chọn đúng search và matching vừa tạo. Kiểm tra bản nháp không tự thêm cam kết độ chính xác, chi phí tiết kiệm hoặc khách hàng tham chiếu.

Các file mẫu chưa được tự động ghi vào database.

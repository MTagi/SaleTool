/**
 * Ô số có sàn.
 *
 * Trình duyệt trả về chuỗi, và chuỗi rỗng parse ra `NaN` — thả `NaN` vào state
 * là ô nhập thành uncontrolled và React chửi. Sáu ô số trong Settings trước đây
 * mỗi ô tự viết lại `parseInt(...) || 1`; gom vào đây để quy tắc chỉ có một chỗ.
 *
 * `integer` chọn parseInt hay parseFloat; `min` vừa là ràng buộc của trình
 * duyệt vừa là giá trị thay thế khi người dùng xoá trắng ô.
 */
export default function NumberField({
  label,
  value,
  onChange,
  min = 0,
  max,
  step,
  integer = true,
  children,
}) {
  function handle(e) {
    const parsed = integer ? parseInt(e.target.value, 10) : parseFloat(e.target.value);
    if (Number.isNaN(parsed)) {
      onChange(min);
      return;
    }
    // Kẹp về khoảng hợp lệ ngay tại đây thay vì chỉ đặt `min`/`max` cho trình
    // duyệt: thuộc tính đó chỉ chặn lúc submit, còn state thì đã nhận giá trị
    // xấu rồi — và "0 trang mỗi công ty" là một cấu hình vô nghĩa.
    onChange(Math.min(max ?? Infinity, Math.max(min, parsed)));
  }

  return (
    <label>
      {label}
      <input type="number" min={min} max={max} step={step} value={value} onChange={handle} />
      {children}
    </label>
  );
}

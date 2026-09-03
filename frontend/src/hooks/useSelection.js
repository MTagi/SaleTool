import { useCallback, useMemo, useState } from "react";

/**
 * Một tập đang được chọn, cùng các thao tác quen thuộc trên nó.
 *
 * Bốn trang đều cần đúng một thứ — tick/bỏ tick một dòng, chọn hết, xoá hết,
 * hỏi "dòng này có được chọn không" — và trước đây mỗi trang tự viết lại theo
 * một kiểu: chỗ dùng `Set`, chỗ dùng mảng, chỗ nhét cả hàm toggle vào giữa JSX.
 * Gom về đây để mọi trang cùng một ngữ nghĩa và cùng cách đọc.
 *
 * Khoá phần tử do caller quyết định (tên công ty, chỉ số trong danh sách…) —
 * hook không giả định gì về kiểu của nó, chỉ cần so sánh được bằng `===`.
 */
export function useSelection(initial = []) {
  const [keys, setKeys] = useState(() => new Set(initial));

  const toggle = useCallback((key) => {
    setKeys((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }, []);

  /** Chọn hết / bỏ hết. `allKeys` truyền vào lúc gọi vì danh sách đổi theo dữ liệu. */
  const setAll = useCallback((on, allKeys) => {
    setKeys(on ? new Set(allKeys) : new Set());
  }, []);

  const replace = useCallback((nextKeys) => setKeys(new Set(nextKeys)), []);
  const clear = useCallback(() => setKeys(new Set()), []);

  return useMemo(
    () => ({
      keys,
      size: keys.size,
      isEmpty: keys.size === 0,
      has: (key) => keys.has(key),
      /** Đã chọn trọn vẹn danh sách này chưa — dùng cho ô tick "chọn tất cả". */
      hasAll: (allKeys) => allKeys.length > 0 && allKeys.every((key) => keys.has(key)),
      toList: () => [...keys],
      toggle,
      setAll,
      replace,
      clear,
    }),
    [keys, toggle, setAll, replace, clear],
  );
}

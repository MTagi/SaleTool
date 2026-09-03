/** Một ô tick kèm nhãn — dạng lặp lại nhiều nhất trong Settings. */
export default function CheckboxField({ checked, onChange, children }) {
  return (
    <label className="checkbox">
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
      {children}
    </label>
  );
}

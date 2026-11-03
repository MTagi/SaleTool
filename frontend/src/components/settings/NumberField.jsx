/**
 * Numeric input with a minimum value.
 *
 * Browsers return strings, and parsing an empty string produces `NaN`. Putting
 * `NaN` in state makes the input uncontrolled and triggers a React warning. The
 * six numeric Settings fields previously repeated `parseInt(...) || 1`; keep the
 * rule in one place.
 *
 * `integer` selects parseInt or parseFloat. `min` is both the browser constraint
 * and the fallback value when the user clears the field.
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
    // Clamp to the valid range here instead of relying only on the browser's
    // `min`/`max`: those are checked on submit, after state already received the
    // invalid value. "Zero pages per company" is not a meaningful configuration.
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

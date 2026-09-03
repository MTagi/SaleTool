/**
 * A table row plus the detail row that opens under it.
 *
 * Both halves must be siblings inside the same <tbody> — wrapping them in a
 * <div> would be invalid HTML and the browser hoists the div out of the table,
 * which is why this exists as a fragment component instead of a wrapper.
 *
 * `detail` is a <td colSpan=…>, not its <tr>: the caller owns the column count.
 */
export default function ExpandableRow({ row, detail, open }) {
  return (
    <>
      {row}
      {open && <tr className="detail-row">{detail}</tr>}
    </>
  );
}

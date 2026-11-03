import { useEffect, useRef } from "react";

export default function ConfirmDialog({
  open,
  title,
  body,
  busy = false,
  onClose,
  onConfirm,
  confirmLabel = "Delete",
  tone = "danger",
}) {
  const ref = useRef(null);
  useEffect(() => {
    if (!open) return;
    const dialog = ref.current;
    const focused = document.activeElement;
    const overflow = document.body.style.overflow;
    dialog.showModal();
    document.body.style.overflow = "hidden";
    return () => {
      dialog.close();
      document.body.style.overflow = overflow;
      focused?.focus();
    };
  }, [open]);
  if (!open) return null;
  return (
    <dialog
      ref={ref}
      className="confirm-dialog"
      onClose={onClose}
      onCancel={(e) => {
        if (!busy) return;
        e.preventDefault();
      }}
    >
      <section className="card2">
        <header>
          <h2>{title}</h2>
        </header>
        <p className="muted small" style={{ padding: "16px 20px" }}>{body}</p>
        <div className="toolbar form-actions company-picker-footer">
          <button type="button" className={tone === "danger" ? "link-button danger" : "primary"} disabled={busy} onClick={onConfirm}>
            {busy ? `${confirmLabel}…` : confirmLabel}
          </button>
          <button type="button" className="secondary" disabled={busy} onClick={onClose}>
            Cancel
          </button>
        </div>
      </section>
    </dialog>
  );
}

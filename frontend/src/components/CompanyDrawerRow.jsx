import { Children, useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

export default function CompanyDrawerRow({ row, detail, open, title, onClose, onEnrich, enriching }) {
  const closeButton = useRef(null);
  const drawer = useRef(null);
  const [tab, setTab] = useState("Overview");
  const close = useRef(onClose);
  close.current = onClose;
  useEffect(() => {
    if (!open) return;
    const previous = document.activeElement;
    closeButton.current?.focus();
    function onKey(event) {
      if (event.key === "Escape") close.current();
    }
    function onOutsideClick(event) {
      if (!drawer.current?.contains(event.target)) close.current();
    }
    document.addEventListener("keydown", onKey);
    document.addEventListener("click", onOutsideClick, true);
    return () => {
      document.removeEventListener("keydown", onKey);
      document.removeEventListener("click", onOutsideClick, true);
      if (previous?.isConnected) previous.focus();
    };
  }, [open]);
  return <>{row}{open && createPortal(
    <section ref={drawer} className="company-drawer" role="dialog" aria-modal="false" aria-label={`${title} details`}>
      <header><div><p className="eyebrow">Company details</p><h2>{title}</h2></div><button ref={closeButton} aria-label="Close company details" onClick={onClose}>×</button></header>
      <nav className="detail-tabs" aria-label="Company sections">{["Overview", "Contacts", "Enrichment"].map(label => <button key={label} aria-pressed={tab === label} onClick={() => setTab(label)}>{label}</button>)}</nav>
      <div className="company-drawer-body">{Children.toArray(detail.props.children).filter(child => (child.props["data-pane"] || "Overview") === tab)}</div>
      <footer><button className="primary" disabled={enriching} onClick={onEnrich}>{enriching ? "Starting…" : "Enrich company"}</button><button className="secondary" onClick={() => setTab("Contacts")}>View contacts</button></footer>
    </section>, document.body
  )}</>;
}

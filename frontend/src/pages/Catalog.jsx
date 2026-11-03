import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";
import ConfirmDialog from "../components/ConfirmDialog";
import { useToast } from "../context/ToastContext";
import { useAppStatus } from "../context/StatusContext";

const EMPTY_SERVICE = {
  name: "",
  category: "",
  description: "",
  value_proposition: "",
  target_industries: "",
  target_company_size: "",
  keywords: "",
  active: true,
};

/** Comma-separated input <-> list of strings. */
function splitList(value) {
  return value
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function toForm(service) {
  return {
    name: service.name || "",
    category: service.category || "",
    description: service.description || "",
    value_proposition: service.value_proposition || "",
    target_industries: (service.target_industries || []).join(", "),
    target_company_size: service.target_company_size || "",
    keywords: (service.keywords || []).join(", "),
    active: service.active !== false,
  };
}

function toPayload(form) {
  return {
    name: form.name.trim(),
    category: form.category.trim() || null,
    description: form.description.trim(),
    value_proposition: form.value_proposition.trim() || null,
    target_industries: splitList(form.target_industries),
    target_company_size: form.target_company_size.trim() || null,
    keywords: splitList(form.keywords),
    active: form.active,
  };
}

/**
 * How complete a service description is. Matching quality depends almost
 * entirely on this: the model only sees what is written here, so a service with
 * just a name gets scored on a name.
 */
function completeness(service) {
  const filled = [
    service.description,
    service.value_proposition,
    service.target_industries?.length,
    service.target_company_size,
    service.keywords?.length,
  ].filter(Boolean).length;
  if (filled >= 4) return { label: "Detailed", className: "badge good" };
  if (filled >= 2) return { label: "Usable", className: "badge" };
  return { label: "Too thin", className: "badge bad" };
}

export default function Catalog() {
  const { refresh: refreshStatus } = useAppStatus();
  const { show } = useToast();
  const [services, setServices] = useState(null);
  const [form, setForm] = useState(EMPTY_SERVICE);
  const [editingId, setEditingId] = useState(null);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [saving, setSaving] = useState(false);
  const [formOpen, setFormOpen] = useState(false);
  const [dirty, setDirty] = useState(false);
  const dialogRef = useRef(null);
  const [pendingDelete, setPendingDelete] = useState(null);

  useEffect(() => {
    if (!formOpen) return;
    const dialog = dialogRef.current;
    const focused = document.activeElement;
    const overflow = document.body.style.overflow;
    dialog.showModal();
    document.body.style.overflow = "hidden";
    return () => {
      dialog.close();
      document.body.style.overflow = overflow;
      focused?.focus();
    };
  }, [formOpen]);

  function startAdd() {
    setEditingId(null);
    setForm(EMPTY_SERVICE);
    setDirty(false);
    setError(null);
    setNotice(null);
    setFormOpen(true);
  }

  function requestClose() {
    if (saving) return;
    if (dirty && !window.confirm("Discard unsaved changes?")) return;
    cancelEdit();
    setError(null);
  }

  const load = useCallback(async () => {
    try {
      setServices(await api.listServices());
      // The workflow strip marks this step done from the catalog count.
      refreshStatus();
    } catch (err) {
      setError(err.message || "Couldn't load the catalog.");
    }
  }, [refreshStatus]);

  useEffect(() => {
    load();
  }, [load]);

  function set(field, value) {
    setDirty(true);
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  function startEdit(service) {
    setEditingId(service.id);
    setForm(toForm(service));
    setNotice(null);
    setError(null);
    setDirty(false);
    setFormOpen(true);
  }

  function cancelEdit() {
    setFormOpen(false);
    setDirty(false);
    setEditingId(null);
    setForm(EMPTY_SERVICE);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    if (saving) return;
    setError(null);
    setNotice(null);

    if (!form.name.trim()) {
      setError("Service name is required.");
      return;
    }

    setSaving(true);
    try {
      const payload = toPayload(form);
      if (editingId) {
        await api.updateService(editingId, payload);
        setNotice(`Updated "${payload.name}".`);
      } else {
        await api.createService(payload);
        setNotice(`Added "${payload.name}".`);
      }
      cancelEdit();
      await load();
    } catch (err) {
      setError(err.message || "Couldn't save the service.");
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete() {
    if (!pendingDelete) return;
    setError(null);
    try {
      await api.deleteService(pendingDelete.id);
      if (editingId === pendingDelete.id) cancelEdit();
      show(`Deleted "${pendingDelete.name}" from the catalog.`);
      setPendingDelete(null);
      await load();
    } catch (err) {
      show(err.message || "Couldn't delete the service.", { tone: "error" });
      setPendingDelete(null);
    }
  }

  return (
    <main className="container">
      <div className="page-head">
        <div>
          <h1>Your service catalog</h1>
          <p className="lede">
            Every company gets scored against these. Write them the way you would brief a new
            salesperson: what the service does, who it is for, and what tells you a company needs it.
          </p>
        </div>
        <div className="toolbar">
          <button type="button" className="primary" onClick={startAdd}>Add a service</button>
          <Link to="/matching">Match to companies</Link>
        </div>
      </div>

      {error && !formOpen && <p className="error" role="alert">{error}</p>}
      {notice && <p className="success">{notice}</p>}

      <div className="cols">
        <div>
          <section className="card2">
            <header>
              <h2>Services</h2>
              <span className="hint">
                {services
                  ? `${services.length} total · ${services.filter((s) => s.active).length} offered when matching`
                  : ""}
              </span>
            </header>

            {services === null && !error && <p className="muted cb">Loading…</p>}
            {services?.length === 0 && (
              <div className="empty-state">
                <p>Nothing in the catalog yet.</p>
                <p className="muted small">
                  Use Add a service to create your first entry. Matching and message generation both read this list.
                </p>
              </div>
            )}

            {services && services.length > 0 && (
              <div className="tw">
                <table className="tbl">
                  <thead>
                    <tr>
                      <th>Service</th>
                      <th>Fits</th>
                      <th>Signals</th>
                      <th>Detail</th>
                      <th>Offered</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {services.map((service) => {
                      const quality = completeness(service);
                      return (
                        <tr
                          className={editingId === service.id ? "pick open" : "pick"}
                          key={service.id}
                          style={service.active ? undefined : { opacity: 0.55 }}
                        >
                          <td>
                            <strong>{service.name}</strong>
                            {service.category && <span className="badge"> {service.category}</span>}
                            {service.description && <div className="sub">{service.description}</div>}
                          </td>
                          <td>
                            {service.target_industries?.length > 0 ? (
                              service.target_industries.join(", ")
                            ) : (
                              <span className="muted">—</span>
                            )}
                            {service.target_company_size && (
                              <div className="sub">{service.target_company_size}</div>
                            )}
                          </td>
                          <td className="num">{service.keywords?.length || 0}</td>
                          <td>
                            <span className={quality.className}>{quality.label}</span>
                          </td>
                          <td>{service.active ? <span className="badge on">yes</span> : <span className="badge">no</span>}</td>
                          <td className="nowrap">
                            <button className="link-button" onClick={() => startEdit(service)}>
                              Edit
                            </button>{" "}
                            <button className="link-button danger" onClick={() => setPendingDelete(service)}>
                              Delete
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <ConfirmDialog
            open={Boolean(pendingDelete)}
            title="Delete this service?"
            body={`This removes "${pendingDelete?.name || "this service"}" from the catalog and it will no longer be offered when matching.`}
            busy={false}
            onClose={() => setPendingDelete(null)}
            onConfirm={handleDelete}
            confirmLabel="Delete service"
          />

          {formOpen && <dialog ref={dialogRef} className="catalog-dialog" aria-labelledby="catalog-form-title"
            onCancel={e => { e.preventDefault(); requestClose(); }}>
          <form onSubmit={handleSubmit}>
            <section className="card2">
              <header>
                <h2 id="catalog-form-title">{editingId ? "Edit service" : "Add a service"}</h2>
                <button type="button" className="settings-close" aria-label="Close service form" disabled={saving} onClick={requestClose}>&times;</button>
              </header>
              <fieldset className="cb catalog-fields" disabled={saving}>
                {error && <p className="error" role="alert">{error}</p>}
                <div className="g2">
                  <label>
                    Name
                    <input
                      type="text"
                      required
                      value={form.name}
                      onChange={(e) => set("name", e.target.value)}
                      placeholder="ERP implementation"
                    />
                  </label>
                  <label>
                    Category <span className="muted">— optional</span>
                    <input
                      type="text"
                      value={form.category}
                      onChange={(e) => set("category", e.target.value)}
                      placeholder="Consulting"
                    />
                  </label>
                </div>

                <label>
                  What it does — the problem it solves
                  <textarea
                    rows={3}
                    value={form.description}
                    onChange={(e) => set("description", e.target.value)}
                    placeholder="End-to-end SAP B1 rollout for manufacturers still running finance and inventory on spreadsheets."
                  />
                </label>

                <label>
                  Why buy it from you <span className="muted">— optional</span>
                  <textarea
                    rows={2}
                    value={form.value_proposition}
                    onChange={(e) => set("value_proposition", e.target.value)}
                    placeholder="Go-live in 12 weeks with a fixed price; our team has done 40 rollouts in this industry."
                  />
                </label>

                <div className="g2">
                  <label>
                    Target industries — comma separated
                    <input
                      type="text"
                      value={form.target_industries}
                      onChange={(e) => set("target_industries", e.target.value)}
                      placeholder="Manufacturing, Logistics, Retail"
                    />
                  </label>
                  <label>
                    Target company size
                    <input
                      type="text"
                      value={form.target_company_size}
                      onChange={(e) => set("target_company_size", e.target.value)}
                      placeholder="50-500 employees"
                    />
                  </label>
                </div>

                <label>
                  Buying signals — comma separated
                  <input
                    type="text"
                    value={form.keywords}
                    onChange={(e) => set("keywords", e.target.value)}
                    placeholder="opening new factory, hiring finance staff, legacy ERP, manual reporting"
                  />
                  <span className="muted small-note">
                    Facts about a company that suggest it needs this service. These do the most work
                    in scoring.
                  </span>
                </label>

                <label className="checkbox">
                  <input
                    type="checkbox"
                    checked={form.active}
                    onChange={(e) => set("active", e.target.checked)}
                  />
                  Offer this service when matching
                </label>

              </fieldset>
                <div className="toolbar form-actions catalog-form-footer">
                  <button type="submit" className="primary" disabled={saving}>
                    {saving ? "Saving…" : editingId ? "Save changes" : "Add service"}
                  </button>
                  <button type="button" className="secondary" disabled={saving} onClick={requestClose}>
                      Cancel
                    </button>
                </div>
            </section>
          </form>
          </dialog>}
        </div>

        <div className="rail">
          <section className="card2">
            <header>
              <h2>How scoring reads this</h2>
            </header>
            <div className="cb prose">
              <p>
                <strong>Buying signals</strong> do most of the work. A signal is something the
                enrichment step could plausibly find on a website.
              </p>
              <p>
                <strong>Industry and size</strong> act as a floor, not a veto. A strong signal
                outside your target size still ranks.
              </p>
              <p>
                <strong>Not offered</strong> keeps a service in the catalog but skips it, so a
                seasonal offer need not be deleted.
              </p>
            </div>
          </section>
          <p className="muted small-note">
            The <strong>Detail</strong> column is a rough check on how much the model has to work
            with. A service with only a name gets scored on only a name.
          </p>
        </div>
      </div>
    </main>
  );
}

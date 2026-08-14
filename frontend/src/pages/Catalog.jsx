import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api/client";

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
  if (filled >= 4) return { label: "Detailed", className: "tier-chip" };
  if (filled >= 2) return { label: "Usable", className: "tier-chip" };
  return { label: "Too thin", className: "tier-chip chip-warn" };
}

export default function Catalog() {
  const [services, setServices] = useState(null);
  const [form, setForm] = useState(EMPTY_SERVICE);
  const [editingId, setEditingId] = useState(null);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    load();
  }, []);

  async function load() {
    try {
      setServices(await api.listServices());
    } catch (err) {
      setError(err.message || "Couldn't load the catalog.");
    }
  }

  function set(field, value) {
    setForm((prev) => ({ ...prev, [field]: value }));
  }

  function startEdit(service) {
    setEditingId(service.id);
    setForm(toForm(service));
    setNotice(null);
    setError(null);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  function cancelEdit() {
    setEditingId(null);
    setForm(EMPTY_SERVICE);
  }

  async function handleSubmit(e) {
    e.preventDefault();
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

  async function handleDelete(service) {
    if (!window.confirm(`Delete "${service.name}" from the catalog?`)) return;

    setError(null);
    try {
      await api.deleteService(service.id);
      if (editingId === service.id) cancelEdit();
      setNotice(`Deleted "${service.name}".`);
      await load();
    } catch (err) {
      setError(err.message || "Couldn't delete the service.");
    }
  }

  return (
    <main className="container">
      <div className="results-header">
        <h1>Service catalog</h1>
        <div className="actions">
          <Link to="/matching">Match to companies</Link>
        </div>
      </div>

      <p className="muted">
        The services your company sells. Matching scores every prospect against these, so write them
        the way you would brief a new salesperson — what the service does, who it is for, and what
        tells you a company needs it.
      </p>

      {error && <p className="error">{error}</p>}
      {notice && <p className="success">{notice}</p>}

      <form onSubmit={handleSubmit}>
        <fieldset>
          <legend>{editingId ? "Edit service" : "New service"}</legend>

          <div className="row">
            <label>
              Name
              <input
                type="text"
                value={form.name}
                onChange={(e) => set("name", e.target.value)}
                placeholder="ERP implementation"
              />
            </label>
            <label>
              Category (optional)
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
            Why buy it from you (optional)
            <textarea
              rows={2}
              value={form.value_proposition}
              onChange={(e) => set("value_proposition", e.target.value)}
              placeholder="Go-live in 12 weeks with a fixed price; our team has done 40 rollouts in this industry."
            />
          </label>

          <div className="row">
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
          </label>
          <p className="muted small-note">
            Facts about a company that suggest it needs this service. These do the most work in
            scoring.
          </p>

          <label className="checkbox">
            <input
              type="checkbox"
              checked={form.active}
              onChange={(e) => set("active", e.target.checked)}
            />
            Active — offer this service when matching
          </label>
        </fieldset>

        <div className="actions">
          <button type="submit" className="primary" disabled={saving}>
            {saving ? "Saving…" : editingId ? "Save changes" : "Add service"}
          </button>
          {editingId && (
            <button type="button" className="secondary" onClick={cancelEdit}>
              Cancel
            </button>
          )}
        </div>
      </form>

      <h2 className="section-heading">
        Services {services ? `(${services.length})` : ""}
      </h2>

      {services === null && !error && <p className="muted">Loading…</p>}
      {services?.length === 0 && (
        <p className="muted">Nothing in the catalog yet. Add your first service above.</p>
      )}

      {services?.map((service) => {
        const quality = completeness(service);
        return (
          <div className="company-card" key={service.id}>
            <div className="company-head">
              <span className="company-name">
                {service.name}
                {!service.active && <span className="tier-chip chip-muted"> inactive</span>}
              </span>
              <span className="company-meta">
                {service.category && `${service.category} · `}
                <span className={quality.className}>{quality.label}</span>
              </span>
            </div>

            <div className="enrich-body">
              {service.description && <p className="enrich-description">{service.description}</p>}
              {service.value_proposition && (
                <div className="enrich-detail">
                  <span className="enrich-detail-label">Why buy</span>
                  <span>{service.value_proposition}</span>
                </div>
              )}
              {service.target_industries?.length > 0 && (
                <div className="enrich-detail">
                  <span className="enrich-detail-label">Industries</span>
                  <span>{service.target_industries.join(", ")}</span>
                </div>
              )}
              {service.target_company_size && (
                <div className="enrich-detail">
                  <span className="enrich-detail-label">Size</span>
                  <span>{service.target_company_size}</span>
                </div>
              )}
              {service.keywords?.length > 0 && (
                <div className="enrich-detail">
                  <span className="enrich-detail-label">Signals</span>
                  <span>{service.keywords.join(", ")}</span>
                </div>
              )}

              <div className="actions">
                <button className="link-button" onClick={() => startEdit(service)}>
                  Edit
                </button>
                <button className="link-button danger" onClick={() => handleDelete(service)}>
                  Delete
                </button>
              </div>
            </div>
          </div>
        );
      })}
    </main>
  );
}

import { useState } from "react";
import { getToken } from "../api/client";

async function downloadFile(fmt, runId) {
  const token = getToken();
  const res = await fetch(`/api/download/${fmt}?run_id=${encodeURIComponent(runId)}`, {
    headers: token ? { Authorization: `Bearer ${token}` } : {},
  });
  if (!res.ok) throw new Error(`Không tải được file (${res.status})`);

  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `saletool_results.${fmt}`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}

export default function ResultsView({ companies, totalCompanies, totalContacts, runId }) {
  const [downloadError, setDownloadError] = useState(null);

  async function handleDownload(fmt) {
    setDownloadError(null);
    try {
      await downloadFile(fmt, runId);
    } catch (err) {
      setDownloadError(err.message);
    }
  }

  return (
    <>
      <div className="actions">
        <button className="link-button" onClick={() => handleDownload("csv")}>
          Tải CSV
        </button>
        <button className="link-button" onClick={() => handleDownload("json")}>
          Tải JSON
        </button>
      </div>
      {downloadError && <p className="error">{downloadError}</p>}
      <p className="muted">
        {totalCompanies} công ty · {totalContacts} liên hệ
      </p>

      {companies.length === 0 && <p>Không có công ty nào khớp tiêu chí.</p>}

      {companies.map((r, i) => (
        <div className="company-card" key={r.company.linkedin_url || r.company.name || i}>
          <div className="company-head">
            <span className="company-name">{r.company.name}</span>
            <span className="company-meta">
              {[r.company.industry, r.company.location].filter(Boolean).join(" · ")}
              {r.company.employee_count ? ` · ${r.company.employee_count} nhân sự` : ""}
              {r.company.linkedin_url && (
                <>
                  {" · "}
                  <a href={r.company.linkedin_url} target="_blank" rel="noopener noreferrer">
                    linkedin ↗
                  </a>
                </>
              )}
            </span>
          </div>

          {r.contacts.length === 0 && <p className="muted small">Không tìm thấy liên hệ cấp cao.</p>}

          {r.contacts.map((c, j) => (
            <div className="contact-row" key={c.linkedin_url || c.full_name || j}>
              <span className="contact-name">{c.full_name}</span>
              <span className="contact-title">{c.title || "—"}</span>
              <span className="tier-chip">{c.seniority || "?"}</span>
              {c.linkedin_url && (
                <a href={c.linkedin_url} target="_blank" rel="noopener noreferrer">
                  linkedin ↗
                </a>
              )}
              {c.email && <span className="contact-email">{c.email}</span>}
            </div>
          ))}
        </div>
      ))}
    </>
  );
}

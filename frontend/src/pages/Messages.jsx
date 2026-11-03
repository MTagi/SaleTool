import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import JobProgress from "../components/JobProgress";
import MessageCard from "../components/MessageCard";
import Prerequisites from "../components/Prerequisites";
import { copyText } from "../lib/clipboard";
import { useAppStatus } from "../context/StatusContext";
import { useMessageJob } from "../hooks/useJob";
import { useSelection } from "../hooks/useSelection";
import { formatRun } from "../lib/format";
import { messagesToText } from "../lib/message";
import { allMet } from "../lib/prerequisites";

const LANGUAGE_LABELS = { en: "English", vi: "Vietnamese" };

export default function Messages() {
  const [searchParams, setSearchParams] = useSearchParams();
  const { status, refresh: refreshStatus } = useAppStatus();
  const [runs, setRuns] = useState(null);
  const [options, setOptions] = useState(null);
  const [matchJobs, setMatchJobs] = useState([]);
  const runId = searchParams.get("run") || "";
  const [run, setRun] = useState(null);
  const picked = useSelection();
  const [filter, setFilter] = useState("");
  const [channel, setChannel] = useState("email");
  const [tone, setTone] = useState("direct");
  const [language, setLanguage] = useState("en");
  const [matchJobId, setMatchJobId] = useState("");
  const [instructions, setInstructions] = useState("");
  const [jobId, setJobId] = useState(null);
  const [error, setError] = useState(null);
  const [starting, setStarting] = useState(false);
  const [copiedAll, setCopiedAll] = useState(false);
  const [savedMessageJobs, setSavedMessageJobs] = useState([]);
  const [loadingRun, setLoadingRun] = useState(false);

  const {
    job: loadedJob,
    error: pollError,
    running: polling,
  } = useMessageJob(jobId);
  const job =
    loadedJob?.id === jobId && loadedJob?.run_id === runId ? loadedJob : null;
  const running = Boolean(job) && polling;

  // Arriving from a finished matching run carries both ids in the URL, so the
  // matching context is already selected instead of having to be found again.
  const requestedMatch = searchParams.get("match");

  useEffect(() => {
    let cancelled = false;
    Promise.all([api.listRuns(), api.getMessageOptions()])
      .then(([runList, opts]) => {
        if (cancelled) return;
        setRuns(runList);
        setOptions(opts);
      })
      .catch((err) => {
        if (!cancelled) setError(err.message || "Couldn't load searches.");
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (job?.status === "completed") refreshStatus();
  }, [job?.status, refreshStatus]);

  // Load the run's contacts whenever the selected run changes. A selection from
  // the previous run no longer applies (its indices point to the old list), so
  // clear it. `clearPicked` is stable, while `picked` changes on every click;
  // including `picked` in the dependencies would rerun the effect on each click.
  const clearPicked = picked.clear;
  useEffect(() => {
    let cancelled = false;
    setRun(null);
    setMatchJobs([]);
    setSavedMessageJobs([]);
    setMatchJobId("");
    setJobId(null);
    setFilter("");
    setInstructions("");
    setCopiedAll(false);
    setError(null);
    clearPicked();
    setLoadingRun(Boolean(runId));
    if (!runId) return;
    api
      .getRunHistory(runId)
      .then((history) => {
        if (cancelled) return;
        setRun(history.run);
        setMatchJobs(
          history.match_jobs.filter((item) => item.status === "completed"),
        );
        setSavedMessageJobs(history.message_jobs);
        setJobId(history.message_jobs[0]?.id || null);
      })
      .catch((err) => {
        if (!cancelled)
          setError(err.message || "Couldn't load that search run.");
      })
      .finally(() => {
        if (!cancelled) setLoadingRun(false);
      });
    return () => {
      cancelled = true;
    };
  }, [runId, clearPicked]);

  // A matching run only helps if it scored this same search.
  const usableMatchJobs = useMemo(
    () => matchJobs.filter((j) => j.run_id === runId),
    [matchJobs, runId],
  );

  useEffect(() => {
    const requested = usableMatchJobs.find((j) => j.id === requestedMatch);
    setMatchJobId((requested || usableMatchJobs[0])?.id || "");
  }, [usableMatchJobs, requestedMatch]);

  // Track selection by list index, not by a key made from names: company and
  // person names can contain spaces, making a combined key ambiguous to parse.
  const contacts = useMemo(() => {
    if (!run || run.id !== runId) return [];
    return run.results.flatMap((result) =>
      result.contacts.map((contact) => ({
        companyId: result.company.id,
        companyName: result.company.name,
        companyDomain: result.company.domain,
        contact,
      })),
    );
  }, [run, runId]);

  // Filtering hides rows but must not silently drop what is already ticked —
  // selection stays by index into the full list.
  const visibleContacts = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    const indexed = contacts.map((entry, index) => ({ ...entry, index }));
    if (!needle) return indexed;
    return indexed.filter(
      ({ companyName, contact }) =>
        companyName.toLowerCase().includes(needle) ||
        contact.full_name.toLowerCase().includes(needle) ||
        (contact.title || "").toLowerCase().includes(needle),
    );
  }, [contacts, filter]);

  const channelSpec = options?.channels.find((c) => c.id === channel);

  const checks = [
    {
      ok: status ? status.llm_configured : true,
      label: "No LLM API key — messages are written by a model",
      fix: { to: "/settings", text: "add one in Settings" },
    },
    {
      ok: status ? status.sender_configured : true,
      label:
        "No sender profile — a message needs a name and company to come from",
      fix: { to: "/settings", text: "fill it in under Settings" },
    },
    {
      ok: status ? status.counts.runs > 0 : true,
      label: "No saved searches, so there are no contacts to write to",
      fix: { to: "/", text: "run a search" },
    },
  ];
  const ready = allMet(checks);

  async function copyEverything() {
    setCopiedAll(await copyText(messagesToText(job?.results || [])));
    setTimeout(() => setCopiedAll(false), 2000);
  }

  // Company selection in the dialog selects all contacts for those companies,
  // replacing the current contact selection. Individual contacts can still be
  // adjusted in the table after closing the dialog.
  const companies = useMemo(() => {
    const byCompany = new Map();
    contacts.forEach(({ companyId, companyName, companyDomain }, index) => {
      const entry = byCompany.get(companyId) || { id: companyId, name: companyName, domain: companyDomain, indexes: [] };
      entry.indexes.push(index);
      byCompany.set(companyId, entry);
    });
    return [...byCompany.values()];
  }, [contacts]);

  const [pickerOpen, setPickerOpen] = useState(false);
  const [checkedCompanies, setCheckedCompanies] = useState([]);
  const pickerRef = useRef(null);
  const pickCount = companies.reduce(
    (sum, company) =>
      sum + (checkedCompanies.includes(company.id) ? company.indexes.length : 0),
    0,
  );

  useEffect(() => {
    if (!pickerOpen) return;
    const dialog = pickerRef.current;
    const focused = document.activeElement;
    const overflow = document.body.style.overflow;
    dialog.showModal();
    document.body.style.overflow = "hidden";
    return () => {
      dialog.close();
      document.body.style.overflow = overflow;
      focused?.focus();
    };
  }, [pickerOpen]);

  function openCompanyPicker() {
    const checked = new Set(
      companies
        .filter((company) => company.indexes.some((index) => picked.has(index)))
        .map((company) => company.id),
    );
    setCheckedCompanies([...checked]);
    setPickerOpen(true);
  }

  function toggleCompany(name) {
    setCheckedCompanies((previous) =>
      previous.includes(name)
        ? previous.filter((item) => item !== name)
        : [...previous, name],
    );
  }

  function applyCompanies() {
    const wanted = new Set(checkedCompanies);
    const next = companies.flatMap((company) =>
      wanted.has(company.id) ? company.indexes : [],
    );
    picked.replace(next);
    setPickerOpen(false);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);

    if (!runId || run?.id !== runId || loadingRun) {
      setError("Choose a search run and wait for its contacts to load.");
      return;
    }
    if (picked.isEmpty) {
      setError("Pick at least one contact.");
      return;
    }

    setStarting(true);
    try {
      const targets = picked.toList().map((index) => ({
        company_id: contacts[index].companyId,
        contact_id: contacts[index].contact.id,
        company_name: contacts[index].companyName,
        contact_name: contacts[index].contact.full_name,
      }));
      const created = await api.startMessages({
        run_id: runId,
        targets,
        channel,
        tone,
        language,
        match_job_id: matchJobId || null,
        custom_instructions: instructions.trim() || null,
      });
      setSavedMessageJobs((previous) => [
        {
          id: created.job_id,
          run_id: runId,
          created_at: new Date().toISOString(),
          status: created.status,
          channel,
          language,
          tone,
        },
        ...previous,
      ]);
      setJobId(created.job_id);
    } catch (err) {
      setError(err.message || "Couldn't start message generation.");
    } finally {
      setStarting(false);
    }
  }

  return (
    <main className="container">
      <div className="page-head">
        <div>
          <h1>Write first-touch messages</h1>
          <p className="lede">
            Choose one search run first. Contacts, matching context and saved
            drafts are shown only for that search.
          </p>
        </div>
        <div className="toolbar">
          <Link to="/matching">Matching</Link>
          <Link to="/settings">Sender profile</Link>
        </div>
      </div>

      {error && <p className="error">{error}</p>}
      {jobId && pollError && <p className="error">{pollError}</p>}

      <Prerequisites checks={checks} />

      <div className="cols">
        <form id="messages-form" onSubmit={handleSubmit}>
          <section className="card2">
            <header>
              <h2>Setup</h2>
            </header>
            <div className="cb">
              <div className="g2">
                <label>
                  Search run
                  <select
                    value={runId}
                    disabled={starting}
                    onChange={(e) =>
                      setSearchParams(
                        e.target.value ? { run: e.target.value } : {},
                      )
                    }
                  >
                    <option value="">
                      {runs === null ? "Loading…" : "Choose a search run"}
                    </option>
                    {runId && !runs?.some((item) => item.id === runId) && (
                      <option value={runId}>
                        {run?.id === runId
                          ? formatRun(run, "contacts")
                          : "Selected search run"}
                      </option>
                    )}
                    {runs?.map((r) => (
                      <option key={r.id} value={r.id}>
                        {formatRun(r, "contacts")}
                      </option>
                    ))}
                  </select>
                </label>
                <div>
                  <label>
                    Reason for writing
                    <select
                      value={matchJobId}
                      disabled={!runId || loadingRun}
                      onChange={(e) => setMatchJobId(e.target.value)}
                    >
                      <option value="">
                        None — write without a per-company reason
                      </option>
                      {usableMatchJobs.map((j) => (
                        <option key={j.id} value={j.id}>
                          {new Date(j.created_at).toLocaleString()} ·{" "}
                          {j.completed} companies scored
                        </option>
                      ))}
                    </select>
                  </label>
                  <p className="muted small-note">
                    {usableMatchJobs.length === 0
                      ? "No completed matching run for this search yet — running Matching first gives each message a specific opening line."
                      : "Supplies the best-fit service and the reason it fits, which is what the opening line is built from."}
                  </p>
                </div>
              </div>

              <div className="g3">
                <div>
                  <label>
                    Channel
                    <select
                      value={channel}
                      onChange={(e) => setChannel(e.target.value)}
                    >
                      {options?.channels.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.label}
                        </option>
                      ))}
                    </select>
                  </label>
                  {channelSpec && (
                    <p className="muted small-note">
                      {channelSpec.guidance}
                      {channelSpec.max_body_chars &&
                        ` Hard limit ${channelSpec.max_body_chars} characters.`}
                      {channelSpec.max_body_words &&
                        ` Target under ${channelSpec.max_body_words} words.`}
                    </p>
                  )}
                </div>
                <label>
                  Tone
                  <select
                    value={tone}
                    onChange={(e) => setTone(e.target.value)}
                  >
                    {options?.tones.map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Language
                  <select
                    value={language}
                    onChange={(e) => setLanguage(e.target.value)}
                  >
                    {options?.languages.map((l) => (
                      <option key={l} value={l}>
                        {LANGUAGE_LABELS[l] || l}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              <label>
                Extra instructions <span className="muted">— optional</span>
                <input
                  type="text"
                  value={instructions}
                  onChange={(e) => setInstructions(e.target.value)}
                  placeholder="Mention we'll be at the Hanoi manufacturing expo next month"
                />
              </label>
            </div>
          </section>

          <section className="card2">
            <header>
              <h2>Who to write to</h2>
              <span className="hint">
                {picked.size} of {contacts.length} selected
              </span>
            </header>

            {!runId && (
              <p className="muted small cb">
                Choose a search run above to load its contacts and saved drafts.
              </p>
            )}
            {loadingRun && (
              <p className="muted small cb">Loading this search…</p>
            )}
            {run?.id === runId && contacts.length === 0 && (
              <p className="muted small cb">
                This run has no contacts to write to.
              </p>
            )}

            {contacts.length > 0 && (
              <>
                <div className="cb cb-tight">
                  <div className="toolbar">
                    <button
                      type="button"
                      className="secondary"
                      onClick={openCompanyPicker}
                    >
                      Select companies
                    </button>
                    <button
                      type="button"
                      className="link-button"
                      onClick={picked.clear}
                    >
                      Clear
                    </button>
                    <input
                      type="text"
                      className="filter-input"
                      value={filter}
                      onChange={(e) => setFilter(e.target.value)}
                      placeholder="Filter by name, title or company"
                      aria-label="Filter contacts"
                    />
                  </div>
                  {filter &&
                    picked.size >
                      visibleContacts.filter((c) => picked.has(c.index))
                        .length && (
                      <p className="muted small-note">
                        Some selected contacts are hidden by the filter — they
                        are still included.
                      </p>
                    )}
                </div>

                <div className="tw">
                  <table className="tbl">
                    <thead>
                      <tr>
                        <th className="tick" />
                        <th>Contact</th>
                        <th>Title</th>
                        <th>Company</th>
                        <th>Reachable by</th>
                      </tr>
                    </thead>
                    <tbody>
                      {visibleContacts.length === 0 && (
                        <tr>
                          <td colSpan={5} className="muted">
                            No contact matches “{filter}”.
                          </td>
                        </tr>
                      )}
                      {visibleContacts.map(
                        ({ companyName, contact, index }) => (
                          <tr
                            className="pick"
                            key={`${companyName}-${contact.full_name}-${index}`}
                          >
                            <td>
                              <input
                                type="checkbox"
                                checked={picked.has(index)}
                                onChange={() => picked.toggle(index)}
                                aria-label={`Select ${contact.full_name}`}
                              />
                            </td>
                            <td>
                              <strong>{contact.full_name}</strong>
                            </td>
                            <td>
                              {contact.title || (
                                <span className="muted">—</span>
                              )}
                            </td>
                            <td>{companyName}</td>
                            <td>
                              {contact.email && (
                                <span className="badge">email</span>
                              )}{" "}
                              {contact.linkedin_url && (
                                <span className="badge">LinkedIn</span>
                              )}
                              {!contact.email && !contact.linkedin_url && (
                                <span className="muted">—</span>
                              )}
                            </td>
                          </tr>
                        ),
                      )}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </section>
          <dialog
            ref={pickerRef}
            className="company-picker-dialog"
            aria-labelledby="company-picker-title"
            onClose={() => setPickerOpen(false)}
          >
            <section className="card2">
              <header>
                <h2 id="company-picker-title">Select companies</h2>
                <button
                  type="button"
                  className="settings-close"
                  aria-label="Close company picker"
                  onClick={() => setPickerOpen(false)}
                >
                  &times;
                </button>
              </header>
              <div className="cb company-picker-body">
                <p className="muted small">
                  Checking a company selects every saved contact found for it;
                  unchecking removes them. Fine-tune individual contacts after
                  closing.
                </p>
                <div className="toolbar">
                  <button
                    type="button"
                    className="secondary"
                    onClick={() =>
                      setCheckedCompanies(companies.map((company) => company.id))
                    }
                  >
                    Select all
                  </button>
                  <button
                    type="button"
                    className="link-button"
                    onClick={() => setCheckedCompanies([])}
                  >
                    Clear
                  </button>
                </div>
                {companies.length === 0 && (
                  <p className="muted">No companies loaded yet.</p>
                )}
                <ul className="company-picker-list">
                  {companies.map((company) => (
                    <li key={company.id}>
                      <label className="checkbox company-picker-row">
                        <input
                          type="checkbox"
                          checked={checkedCompanies.includes(company.id)}
                          onChange={() => toggleCompany(company.id)}
                        />
                        <strong>{company.name}</strong>{company.domain && <span className="muted"> · {company.domain}</span>}
                        <span className="count">
                          {company.indexes.length}{" "}
                          {company.indexes.length === 1 ? "contact" : "contacts"}
                        </span>
                      </label>
                    </li>
                  ))}
                </ul>
              </div>
              <div className="toolbar form-actions company-picker-footer">
                <button type="button" className="primary" onClick={applyCompanies}>
                  Select {pickCount} {pickCount === 1 ? "contact" : "contacts"}
                </button>
                <button
                  type="button"
                  className="secondary"
                  onClick={() => setPickerOpen(false)}
                >
                  Cancel
                </button>
              </div>
            </section>
          </dialog>
        </form>

        <div className="rail">
          <section className="card2">
            <header>
              <h2>Before you run</h2>
            </header>
            <div className="cb">
              <div className="rail-big">
                {picked.size}
                <span>{picked.size === 1 ? "contact" : "contacts"}</span>
              </div>
              <p className="muted small-note">1 model call each</p>
              <div className="rail-row">
                <span className="k">Channel</span>
                <span>{channelSpec?.label || channel}</span>
              </div>
              <div className="rail-row">
                <span className="k">Per-company reason</span>
                <span>{matchJobId ? "yes" : "no"}</span>
              </div>
              <button
                type="submit"
                form="messages-form"
                className="primary"
                disabled={
                  starting ||
                  running ||
                  !ready ||
                  !runId ||
                  run?.id !== runId ||
                  loadingRun ||
                  picked.isEmpty
                }
              >
                {starting
                  ? "Starting…"
                  : running
                    ? "Writing…"
                    : `Write ${picked.size || ""} draft${picked.size === 1 ? "" : "s"}`}
              </button>
              {!ready && (
                <p className="muted small-note">
                  Finish the steps above first.
                </p>
              )}
              <p className="muted small-note">
                Nothing is sent. Drafts stay here until you copy or export them.
              </p>
            </div>
          </section>
        </div>
      </div>

      {run?.id === runId && savedMessageJobs.length > 0 && (
        <section className="card2" aria-label="Saved drafts for this search">
          <header>
            <h2>Saved drafts for this search</h2>
          </header>
          <form className="cb" onSubmit={(event) => event.preventDefault()}>
            <label>
              Message run
              <select
                value={jobId || ""}
                disabled={starting}
                onChange={(event) => {
                  setJobId(event.target.value);
                  setCopiedAll(false);
                }}
              >
                {savedMessageJobs.map((item) => (
                  <option key={item.id} value={item.id}>
                    {new Date(item.created_at).toLocaleString()} ·{" "}
                    {item.channel} · {item.language}
                  </option>
                ))}
              </select>
            </label>
          </form>
        </section>
      )}
      {job && (
        <section className="after">
          {job.notices?.length > 0 && (
            <ul className="message-warnings">
              {job.notices.map((notice, i) => (
                <li key={i}>{notice}</li>
              ))}
            </ul>
          )}
          <JobProgress job={job} label="Writing" />

          {job.status === "completed" && job.completed > 0 && (
            <div className="nextbar">
              <span>
                {job.completed} draft{job.completed === 1 ? "" : "s"} ready.
                Read each one before sending — they are drafts, not outbox
                items.
              </span>
              <button
                type="button"
                className="secondary"
                onClick={copyEverything}
              >
                {copiedAll ? "Copied all" : "Copy all"}
              </button>
            </div>
          )}

          {job.results?.map((message, i) => (
            <MessageCard
              key={`${message.company_name}-${message.contact_name}-${i}`}
              message={message}
            />
          ))}
        </section>
      )}
    </main>
  );
}

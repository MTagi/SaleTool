import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { api } from "../api/client";
import JobProgress from "../components/JobProgress";
import MessageCard, { messageToText } from "../components/MessageCard";
import Prerequisites, { allMet } from "../components/Prerequisites";
import { copyText } from "../lib/clipboard";
import { useAppStatus } from "../context/StatusContext";
import { useMessageJob } from "../hooks/useJob";

const LANGUAGE_LABELS = { en: "English", vi: "Tiếng Việt" };

function formatRun(run) {
  const criteria = [
    run.criteria.keywords?.join(", "),
    run.criteria.industries?.join(", "),
    run.criteria.locations?.join(", "),
  ]
    .filter(Boolean)
    .join(" · ");
  const when = new Date(run.created_at).toLocaleString();
  return `${criteria || "(no criteria)"} — ${run.total_contacts} contacts — ${when}`;
}

export default function Messages() {
  const [searchParams] = useSearchParams();
  const { status, refresh: refreshStatus } = useAppStatus();
  const [runs, setRuns] = useState(null);
  const [options, setOptions] = useState(null);
  const [matchJobs, setMatchJobs] = useState([]);
  const [runId, setRunId] = useState("");
  const [run, setRun] = useState(null);
  const [selected, setSelected] = useState([]);
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

  const { job, error: pollError } = useMessageJob(jobId);

  // Arriving from a finished matching run carries both ids in the URL, so the
  // matching context is already selected instead of having to be found again.
  const requestedRun = searchParams.get("run");
  const requestedMatch = searchParams.get("match");

  useEffect(() => {
    Promise.all([api.listRuns(), api.getMessageOptions(), api.listMatchJobs()])
      .then(([runList, opts, jobList]) => {
        setRuns(runList);
        setOptions(opts);
        setMatchJobs(jobList.filter((j) => j.status === "completed"));
        const preselect = runList.find((r) => r.id === requestedRun) || runList[0];
        if (preselect) setRunId(preselect.id);
      })
      .catch((err) => setError(err.message || "Couldn't load searches."));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    if (job?.status === "completed") refreshStatus();
  }, [job?.status, refreshStatus]);

  // Load the run's contacts whenever the selected run changes.
  useEffect(() => {
    if (!runId) {
      setRun(null);
      return;
    }
    setSelected([]);
    api
      .getRun(runId)
      .then(setRun)
      .catch((err) => setError(err.message || "Couldn't load that search run."));
  }, [runId]);

  // A matching run only helps if it scored this same search.
  const usableMatchJobs = useMemo(
    () => matchJobs.filter((j) => j.run_id === runId),
    [matchJobs, runId]
  );

  useEffect(() => {
    const requested = usableMatchJobs.find((j) => j.id === requestedMatch);
    setMatchJobId((requested || usableMatchJobs[0])?.id || "");
  }, [usableMatchJobs, requestedMatch]);

  const contacts = useMemo(() => {
    if (!run) return [];
    return run.results.flatMap((result) =>
      result.contacts.map((contact) => ({ companyName: result.company.name, contact }))
    );
  }, [run]);

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
        (contact.title || "").toLowerCase().includes(needle)
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
      label: "No sender profile — a message needs a name and company to come from",
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
    const text = (job?.results || [])
      .filter((m) => !m.error)
      .map((m) => `--- ${m.contact_name} (${m.company_name}) ---\n${messageToText(m)}`)
      .join("\n\n");
    setCopiedAll(await copyText(text));
    setTimeout(() => setCopiedAll(false), 2000);
  }

  // Selection is by index into `contacts`, not by a composed string key:
  // company and contact names both contain spaces, so a string key would have
  // to be split apart again and would break on the first two-word name.
  function toggle(index) {
    setSelected((prev) =>
      prev.includes(index) ? prev.filter((i) => i !== index) : [...prev, index]
    );
  }

  // Apollo's numbers: one or two contacts per account replies roughly twice as
  // well as blanketing everyone, so make that the one-click option.
  function selectTopPerCompany(limit) {
    const perCompany = {};
    const picks = [];
    contacts.forEach(({ companyName }, index) => {
      perCompany[companyName] = (perCompany[companyName] || 0) + 1;
      if (perCompany[companyName] <= limit) picks.push(index);
    });
    setSelected(picks);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);

    if (selected.length === 0) {
      setError("Pick at least one contact.");
      return;
    }

    setStarting(true);
    try {
      const targets = selected.map((index) => ({
        company_name: contacts[index].companyName,
        contact_name: contacts[index].contact.full_name,
      }));
      const { job_id } = await api.startMessages({
        run_id: runId,
        targets,
        channel,
        tone,
        language,
        match_job_id: matchJobId || null,
        custom_instructions: instructions.trim() || null,
      });
      setJobId(job_id);
    } catch (err) {
      setError(err.message || "Couldn't start message generation.");
    } finally {
      setStarting(false);
    }
  }

  const running = job && (job.status === "pending" || job.status === "running");

  return (
    <main className="container">
      <div className="results-header">
        <h1>Generate messages</h1>
        <div className="actions">
          <Link to="/matching">Matching</Link>
          <Link to="/settings">Sender profile</Link>
        </div>
      </div>

      <p className="muted">
        Writes a first-touch message for each contact you pick, using what the tool already knows
        about their company. One LLM call per contact. Every draft is checked against the real
        channel limits before you see it.
      </p>

      {error && <p className="error">{error}</p>}
      {pollError && <p className="error">{pollError}</p>}

      <Prerequisites checks={checks} />

      <form onSubmit={handleSubmit}>
        <fieldset>
          <legend>Contacts</legend>
          <label>
            Search run
            <select value={runId} onChange={(e) => setRunId(e.target.value)}>
              {runs === null && <option value="">Loading…</option>}
              {runs?.length === 0 && <option value="">No searches yet</option>}
              {runs?.map((r) => (
                <option key={r.id} value={r.id}>
                  {formatRun(r)}
                </option>
              ))}
            </select>
          </label>

          {run && contacts.length === 0 && (
            <p className="muted small-note">This run has no contacts to write to.</p>
          )}

          {contacts.length > 0 && (
            <>
              <div className="picker-toolbar">
                <input
                  type="text"
                  className="picker-filter"
                  value={filter}
                  onChange={(e) => setFilter(e.target.value)}
                  placeholder={`Filter ${contacts.length} contacts by name, title or company`}
                  aria-label="Filter contacts"
                />
                <div className="actions">
                  <button type="button" className="link-button" onClick={() => selectTopPerCompany(1)}>
                    Pick 1 per company
                  </button>
                  <button type="button" className="link-button" onClick={() => selectTopPerCompany(2)}>
                    Pick 2 per company
                  </button>
                  <button type="button" className="link-button" onClick={() => setSelected([])}>
                    Clear
                  </button>
                  <span className="muted small">
                    <strong>{selected.length}</strong> selected
                  </span>
                </div>
              </div>

              <div className="contact-picker">
                {visibleContacts.length === 0 && (
                  <p className="muted small" style={{ padding: "8px" }}>
                    No contact matches “{filter}”.
                  </p>
                )}
                {visibleContacts.map(({ companyName, contact, index }) => (
                  <label className="contact-pick" key={`${companyName}-${contact.full_name}-${index}`}>
                    <input
                      type="checkbox"
                      checked={selected.includes(index)}
                      onChange={() => toggle(index)}
                    />
                    <span className="contact-name">{contact.full_name}</span>
                    <span className="contact-title">{contact.title || "—"}</span>
                    <span className="muted small">{companyName}</span>
                  </label>
                ))}
              </div>
              {filter && selected.length > visibleContacts.filter((c) => selected.includes(c.index)).length && (
                <p className="muted small-note">
                  Some selected contacts are hidden by the filter — they are still included.
                </p>
              )}
            </>
          )}
        </fieldset>

        <fieldset>
          <legend>Message</legend>
          <div className="row">
            <label>
              Channel
              <select value={channel} onChange={(e) => setChannel(e.target.value)}>
                {options?.channels.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Tone
              <select value={tone} onChange={(e) => setTone(e.target.value)}>
                {options?.tones.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Language
              <select value={language} onChange={(e) => setLanguage(e.target.value)}>
                {options?.languages.map((l) => (
                  <option key={l} value={l}>
                    {LANGUAGE_LABELS[l] || l}
                  </option>
                ))}
              </select>
            </label>
          </div>

          {channelSpec && (
            <p className="muted small-note">
              {channelSpec.guidance}
              {channelSpec.max_body_chars && ` Hard limit ${channelSpec.max_body_chars} characters.`}
              {channelSpec.max_body_words && ` Target under ${channelSpec.max_body_words} words.`}
            </p>
          )}

          <label>
            Use a matching run for context
            <select value={matchJobId} onChange={(e) => setMatchJobId(e.target.value)}>
              <option value="">None — write without a per-company reason</option>
              {usableMatchJobs.map((j) => (
                <option key={j.id} value={j.id}>
                  {new Date(j.created_at).toLocaleString()} · {j.completed} companies scored
                </option>
              ))}
            </select>
          </label>
          <p className="muted small-note">
            {usableMatchJobs.length === 0
              ? "No completed matching run for this search yet — running Matching first gives each message a specific opening line."
              : "Supplies the best-fit service and the reason it fits, which is what the opening line is built from."}
          </p>

          <label>
            Extra instructions (optional)
            <input
              type="text"
              value={instructions}
              onChange={(e) => setInstructions(e.target.value)}
              placeholder="Mention we'll be at the Hanoi manufacturing expo next month"
            />
          </label>
        </fieldset>

        <button type="submit" className="primary" disabled={starting || running || !ready}>
          {starting
            ? "Starting…"
            : running
              ? "Writing…"
              : `Write ${selected.length || ""} message${selected.length === 1 ? "" : "s"}`}
        </button>
        {!ready && <p className="muted small-note">Finish the steps above first.</p>}
      </form>

      {job && (
        <section className="enrich-results">
          {job.notices?.length > 0 && (
            <ul className="message-warnings">
              {job.notices.map((notice, i) => (
                <li key={i}>{notice}</li>
              ))}
            </ul>
          )}
          <JobProgress job={job} label="Writing" />

          {job.status === "completed" && job.completed > 0 && (
            <div className="next-step">
              <span>
                {job.completed} draft{job.completed === 1 ? "" : "s"} ready. Read each one before
                sending — they are drafts, not outbox items.
              </span>
              <button type="button" className="secondary" onClick={copyEverything}>
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

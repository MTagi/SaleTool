import { useEffect, useMemo, useState } from "react";
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

const LANGUAGE_LABELS = { en: "English", vi: "Tiếng Việt" };

export default function Messages() {
  const [searchParams] = useSearchParams();
  const { status, refresh: refreshStatus } = useAppStatus();
  const [runs, setRuns] = useState(null);
  const [options, setOptions] = useState(null);
  const [matchJobs, setMatchJobs] = useState([]);
  const [runId, setRunId] = useState("");
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

  const { job, error: pollError, running } = useMessageJob(jobId);

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

  // Load the run's contacts whenever the selected run changes. Đổi run thì tập
  // đang chọn không còn nghĩa gì nữa (chỉ số trỏ vào danh sách cũ), nên xoá luôn.
  // `clearPicked` tách ra vì nó ổn định, còn `picked` đổi theo mỗi lần tick —
  // để nguyên `picked` trong deps là effect chạy lại sau mỗi cú tick.
  const clearPicked = picked.clear;
  useEffect(() => {
    if (!runId) {
      setRun(null);
      return;
    }
    clearPicked();
    api
      .getRun(runId)
      .then(setRun)
      .catch((err) => setError(err.message || "Couldn't load that search run."));
  }, [runId, clearPicked]);

  // A matching run only helps if it scored this same search.
  const usableMatchJobs = useMemo(
    () => matchJobs.filter((j) => j.run_id === runId),
    [matchJobs, runId]
  );

  useEffect(() => {
    const requested = usableMatchJobs.find((j) => j.id === requestedMatch);
    setMatchJobId((requested || usableMatchJobs[0])?.id || "");
  }, [usableMatchJobs, requestedMatch]);

  // Tick theo *chỉ số* trong danh sách này, không theo khoá ghép từ tên: tên
  // công ty và tên người đều có dấu cách, nên khoá ghép sẽ phải tách ngược ra và
  // hỏng ngay ở cái tên hai chữ đầu tiên.
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
    setCopiedAll(await copyText(messagesToText(job?.results || [])));
    setTimeout(() => setCopiedAll(false), 2000);
  }

  // Apollo's numbers: one or two contacts per account replies roughly twice as
  // well as blanketing everyone, so make that the one-click option.
  function selectTopPerCompany(limit) {
    const seenPerCompany = {};
    const picks = [];
    contacts.forEach(({ companyName }, index) => {
      seenPerCompany[companyName] = (seenPerCompany[companyName] || 0) + 1;
      if (seenPerCompany[companyName] <= limit) picks.push(index);
    });
    picked.replace(picks);
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);

    if (picked.isEmpty) {
      setError("Pick at least one contact.");
      return;
    }

    setStarting(true);
    try {
      const targets = picked.toList().map((index) => ({
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

  return (
    <main className="container">
      <div className="page-head">
        <div>
          <h1>Write first-touch messages</h1>
          <p className="lede">
            One draft per contact, built from what the earlier steps already know. Every draft is
            re-checked in code against the real channel limits before you see it.
          </p>
        </div>
        <div className="toolbar">
          <Link to="/matching">Matching</Link>
          <Link to="/settings">Sender profile</Link>
        </div>
      </div>

      {error && <p className="error">{error}</p>}
      {pollError && <p className="error">{pollError}</p>}

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
                  Contacts from
                  <select value={runId} onChange={(e) => setRunId(e.target.value)}>
                    {runs === null && <option value="">Loading…</option>}
                    {runs?.length === 0 && <option value="">No searches yet</option>}
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
                </div>
              </div>

              <div className="g3">
                <div>
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
                  {channelSpec && (
                    <p className="muted small-note">
                      {channelSpec.guidance}
                      {channelSpec.max_body_chars &&
                        ` Hard limit ${channelSpec.max_body_chars} characters.`}
                      {channelSpec.max_body_words && ` Target under ${channelSpec.max_body_words} words.`}
                    </p>
                  )}
                </div>
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

            {run && contacts.length === 0 && (
              <p className="muted small cb">This run has no contacts to write to.</p>
            )}

            {contacts.length > 0 && (
              <>
                <div className="cb cb-tight">
                  <div className="toolbar">
                    <button type="button" className="secondary" onClick={() => selectTopPerCompany(1)}>
                      Pick 1 per company
                    </button>
                    <button type="button" className="secondary" onClick={() => selectTopPerCompany(2)}>
                      Pick 2 per company
                    </button>
                    <button type="button" className="link-button" onClick={picked.clear}>
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
                    picked.size > visibleContacts.filter((c) => picked.has(c.index)).length && (
                      <p className="muted small-note">
                        Some selected contacts are hidden by the filter — they are still included.
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
                      {visibleContacts.map(({ companyName, contact, index }) => (
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
                          <td>{contact.title || <span className="muted">—</span>}</td>
                          <td>{companyName}</td>
                          <td>
                            {contact.email && <span className="badge">email</span>}{" "}
                            {contact.linkedin_url && <span className="badge">LinkedIn</span>}
                            {!contact.email && !contact.linkedin_url && (
                              <span className="muted">—</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </section>
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
                disabled={starting || running || !ready}
              >
                {starting
                  ? "Starting…"
                  : running
                    ? "Writing…"
                    : `Write ${picked.size || ""} draft${picked.size === 1 ? "" : "s"}`}
              </button>
              {!ready && <p className="muted small-note">Finish the steps above first.</p>}
              <p className="muted small-note">
                Nothing is sent. Drafts stay here until you copy or export them.
              </p>
            </div>
          </section>
        </div>
      </div>

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

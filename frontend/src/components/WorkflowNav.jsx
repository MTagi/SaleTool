import { useEffect, useRef } from "react";
import { Link, useLocation } from "react-router-dom";

/**
 * The five steps of the pipeline, in order, with what is already done.
 *
 * The nav bar lists pages alphabetically-ish and says nothing about order, so
 * a first-time user has no way to know the catalog must exist before matching,
 * or that messages read from a matching run. This strip is the answer: it shows
 * the sequence and marks each step done as soon as there is data behind it.
 */
function workflowSteps(status) {
  const counts = status?.counts;

  // `blocked` is what this step is still missing. It replaces the hint when set,
  // so the strip doubles as a readiness check — you can see from the nav that
  // Match needs an LLM key without opening Match.
  //
  // Only real blockers go here. Enrich deliberately has none: without an LLM key
  // it still runs layers 0-2 and returns real data, so calling it blocked lies.
  const noLlm = status && !status.llm_configured ? "needs a model key" : null;
  const noService = counts && counts.active_services === 0 ? "no active service" : null;

  return [
    {
      to: "/",
      label: "Search",
      hint: "Find companies",
      done: (counts?.runs ?? 0) > 0,
      blocked: status && !status.data_source_configured ? "needs a provider key" : null,
    },
    {
      to: "/enrichment",
      label: "Enrich",
      hint: "Read their websites",
      done: (counts?.enrich_jobs ?? 0) > 0,
      optional: true,
    },
    {
      to: "/catalog",
      label: "Catalog",
      hint: "Your services",
      done: (counts?.active_services ?? 0) > 0,
      blocked: noService,
    },
    {
      to: "/matching",
      label: "Match",
      hint: "Rank the list",
      done: (counts?.match_jobs ?? 0) > 0,
      blocked: noLlm || noService,
    },
    {
      to: "/messages",
      label: "Message",
      hint: "Write to contacts",
      done: (counts?.message_jobs ?? 0) > 0,
      blocked: noLlm || (status && !status.sender_configured ? "needs a sender profile" : null),
    },
  ];
}

export default function WorkflowNav({ status }) {
  const { pathname } = useLocation();
  const steps = workflowSteps(status);
  const currentRef = useRef(null);

  // On a phone the strip is wider than the screen and scrolls. Without this you
  // can be on step 5 while the strip still shows steps 1-3, which defeats the
  // whole point of having it.
  useEffect(() => {
    currentRef.current?.scrollIntoView({ inline: "center", block: "nearest" });
  }, [pathname]);

  return (
    <nav className="workflow" aria-label="Workflow">
      <ol>
        {steps.map((step, i) => {
          const current = pathname === step.to;
          const classes = ["workflow-step"];
          if (current) classes.push("current");
          if (step.done) classes.push("done");

          return (
            <li
              key={step.to}
              className={classes.join(" ")}
              ref={current ? currentRef : undefined}
            >
              <Link
                to={step.to}
                aria-current={current ? "step" : undefined}
                // Without this the accessible name becomes the number, the
                // label and the hint run together ("4Match Rank the list").
                aria-label={step.blocked ? `${step.label} — ${step.blocked}` : step.label}
              >
                <span className="workflow-index" aria-hidden="true">
                  {step.done ? "✓" : i + 1}
                </span>
                <span className="workflow-text" aria-hidden="true">
                  <span className="workflow-label">{step.label}</span>
                  <span className={`workflow-hint${step.blocked ? " blocked" : ""}`}>
                    {step.blocked || step.hint}
                  </span>
                </span>
              </Link>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

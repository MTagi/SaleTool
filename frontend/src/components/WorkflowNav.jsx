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
export function workflowSteps(status) {
  const counts = status?.counts;
  return [
    {
      to: "/",
      label: "Search",
      hint: "Find companies",
      done: (counts?.runs ?? 0) > 0,
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
    },
    {
      to: "/matching",
      label: "Match",
      hint: "Rank the list",
      done: (counts?.match_jobs ?? 0) > 0,
    },
    {
      to: "/messages",
      label: "Message",
      hint: "Write to contacts",
      done: (counts?.message_jobs ?? 0) > 0,
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
                aria-label={step.label}
              >
                <span className="workflow-index" aria-hidden="true">
                  {step.done ? "✓" : i + 1}
                </span>
                <span className="workflow-text" aria-hidden="true">
                  <span className="workflow-label">{step.label}</span>
                  <span className="workflow-hint">{step.hint}</span>
                </span>
              </Link>
            </li>
          );
        })}
      </ol>
    </nav>
  );
}

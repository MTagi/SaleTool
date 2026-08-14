import { useState } from "react";

// Mirrors MATCH_SCORE_FLOOR in saletool/models.py.
const SCORE_FLOOR = 40;
const STRONG_SCORE = 70;

function scoreClass(score) {
  if (score >= STRONG_SCORE) return "score-strong";
  if (score >= SCORE_FLOOR) return "score-ok";
  return "score-weak";
}

export function ScoreBadge({ score }) {
  return <span className={`score-badge ${scoreClass(score)}`}>{score}</span>;
}

export function CompanyMatchCard({ match }) {
  const [showAll, setShowAll] = useState(false);

  if (match.error) {
    return (
      <div className="company-card">
        <div className="company-head">
          <span className="company-name">
            <span className="rank-number">#{match.rank}</span> {match.company_name}
          </span>
          <span className="company-meta test-fail">not scored</span>
        </div>
        <p className="small muted">{match.error}</p>
      </div>
    );
  }

  const meta = [match.industry, match.location, match.employee_count && `${match.employee_count} employees`]
    .filter(Boolean)
    .join(" · ");

  const otherFits = match.service_fits?.slice(1) || [];

  return (
    <div className="company-card">
      <div className="company-head">
        <span className="company-name">
          <span className="rank-number">#{match.rank}</span> {match.company_name}
          {match.domain && (
            <>
              {" "}
              <a
                className="muted small"
                href={`https://${match.domain}`}
                target="_blank"
                rel="noopener noreferrer"
              >
                {match.domain} ↗
              </a>
            </>
          )}
        </span>
        <span className="company-meta">
          <ScoreBadge score={match.overall_score} />
        </span>
      </div>

      <div className="enrich-body">
        {meta && <p className="muted small" style={{ margin: 0 }}>{meta}</p>}

        {match.best_service_name && (
          <div className="enrich-detail">
            <span className="enrich-detail-label">Best fit</span>
            <span>
              <strong>{match.best_service_name}</strong>
              {match.service_fits?.[0]?.rationale && ` — ${match.service_fits[0].rationale}`}
            </span>
          </div>
        )}

        {match.summary && <p className="enrich-description">{match.summary}</p>}

        {match.signals?.length > 0 && (
          <div className="enrich-detail">
            <span className="enrich-detail-label">Signals</span>
            <ul className="reason-list">
              {match.signals.map((signal, i) => (
                <li key={i}>{signal}</li>
              ))}
            </ul>
          </div>
        )}

        {match.concerns?.length > 0 && (
          <div className="enrich-detail">
            <span className="enrich-detail-label">Concerns</span>
            <ul className="reason-list muted">
              {match.concerns.map((concern, i) => (
                <li key={i}>{concern}</li>
              ))}
            </ul>
          </div>
        )}

        {!match.used_enrichment && (
          <p className="muted small" style={{ margin: 0 }}>
            Scored on search results only — enrich this company for a better-informed score.
          </p>
        )}

        {otherFits.length > 0 && (
          <div className="enrich-sources">
            <button className="link-button" onClick={() => setShowAll((v) => !v)}>
              {showAll ? "Hide" : "Show"} {otherFits.length} more service
              {otherFits.length === 1 ? "" : "s"}
            </button>
            {showAll && (
              <div className="fit-list">
                {otherFits.map((fit) => (
                  <div className="fit-row" key={fit.service_id}>
                    <ScoreBadge score={fit.score} />
                    <span className="fit-name">{fit.service_name}</span>
                    <span className="muted small">{fit.rationale}</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

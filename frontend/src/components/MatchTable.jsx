import { useState } from "react";
import ExpandableRow from "./ExpandableRow";

// Mirrors MATCH_SCORE_FLOOR in saletool/models.py.
const SCORE_FLOOR = 40;
const STRONG_SCORE = 70;

function scoreClass(score) {
  if (score >= STRONG_SCORE) return "score-strong";
  if (score >= SCORE_FLOOR) return "score-ok";
  return "score-weak";
}

function ScoreBadge({ score }) {
  return <span className={`score-badge ${scoreClass(score)}`}>{score}</span>;
}

/**
 * The ranked companies, as a table.
 *
 * Ranking only means something if the scores can be compared, and one tall card
 * per company defeats that — you cannot see rank 2 and rank 9 at once. The row
 * carries what you sort by (rank, score, best service, the one-line reason); the
 * signals, concerns and per-service scores open underneath the row.
 *
 * `selection` là một `useSelection`; bỏ trống thì bảng chỉ để đọc, không có cột
 * tick. `selectableKeys` là những công ty tick được — công ty chấm lỗi không nằm
 * trong đó, nên "chọn tất cả" không bao giờ chọn phải chúng.
 */
export default function MatchTable({ matches, selection, selectableKeys = [] }) {
  const [open, setOpen] = useState(null);

  const selectable = Boolean(selection);

  return (
    <div className="tw">
      <table className="tbl">
        <thead>
          <tr>
            {selectable && (
              <th className="tick">
                <input
                  type="checkbox"
                  checked={selection.hasAll(selectableKeys)}
                  onChange={(e) => selection.setAll(e.target.checked, selectableKeys)}
                  aria-label="Select all companies"
                />
              </th>
            )}
            <th className="rank">#</th>
            <th>Company</th>
            <th>Fit</th>
            <th>Best service</th>
            <th>Why it scored that</th>
          </tr>
        </thead>
        <tbody>
          {matches.map((match) => {
            const isOpen = open === match.company_name;
            const otherFits = match.service_fits?.slice(1) || [];
            const topRationale = match.service_fits?.[0]?.rationale;

            return (
              <ExpandableRow
                key={`${match.company_name}-${match.rank}`}
                open={isOpen}
                row={
                  <tr className={isOpen ? "pick open" : "pick"}>
                    {selectable && (
                      <td>
                        <input
                          type="checkbox"
                          checked={selection.has(match.company_name)}
                          onChange={() => selection.toggle(match.company_name)}
                          aria-label={`Select ${match.company_name}`}
                          disabled={Boolean(match.error)}
                        />
                      </td>
                    )}
                    <td className="num">
                      {match.error ? <span className="muted">—</span> : <strong>{match.rank}</strong>}
                    </td>
                    <td>
                      <strong>{match.company_name}</strong>
                      <div className="sub">
                        {match.domain || "no domain"}
                        {match.industry ? ` · ${match.industry}` : ""}
                      </div>
                    </td>
                    <td>
                      {match.error ? (
                        <span className="badge bad">error</span>
                      ) : (
                        <ScoreBadge score={match.overall_score} />
                      )}
                    </td>
                    <td>{match.best_service_name || <span className="muted">—</span>}</td>
                    <td className="why">
                      {match.error ? (
                        <span className="muted small">{match.error}</span>
                      ) : (
                        <>
                          {topRationale || match.summary || <span className="muted">—</span>}
                          <div className="badge-row">
                            {match.signals?.length > 0 && (
                              <span className="badge">
                                {match.signals.length} signal
                                {match.signals.length === 1 ? "" : "s"}
                              </span>
                            )}
                            {match.used_enrichment ? (
                              <span className="badge on">enriched</span>
                            ) : (
                              <span className="badge">scored on search data only</span>
                            )}
                            <button className="link-button" onClick={() => setOpen(isOpen ? null : match.company_name)}>
                              {isOpen ? "Hide" : "Details"}
                            </button>
                          </div>
                        </>
                      )}
                    </td>
                  </tr>
                }
                detail={
                  <td colSpan={selectable ? 6 : 5}>
                    {match.summary && <p className="lead-para">{match.summary}</p>}

                    {match.signals?.length > 0 && (
                      <>
                        <span className="field-label">Signals</span>
                        <ul className="reason-list">
                          {match.signals.map((signal, i) => (
                            <li key={i}>{signal}</li>
                          ))}
                        </ul>
                      </>
                    )}

                    {match.concerns?.length > 0 && (
                      <>
                        <span className="field-label">Concerns</span>
                        <ul className="reason-list muted">
                          {match.concerns.map((concern, i) => (
                            <li key={i}>{concern}</li>
                          ))}
                        </ul>
                      </>
                    )}

                    {!match.used_enrichment && (
                      <p className="muted small">
                        Scored on search results only — enrich this company for a better-informed
                        score.
                      </p>
                    )}

                    {otherFits.length > 0 && (
                      <>
                        <span className="field-label">Other services</span>
                        <div className="fit-list">
                          {otherFits.map((fit) => (
                            <div className="fit-row" key={fit.service_id}>
                              <ScoreBadge score={fit.score} />
                              <span className="fit-name">{fit.service_name}</span>
                              <span className="muted small">{fit.rationale}</span>
                            </div>
                          ))}
                        </div>
                      </>
                    )}
                  </td>
                }
              />
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

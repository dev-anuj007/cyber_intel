import React, { useEffect, useState } from "react";
import { api } from "../../api";
import { Account, PriorityTier } from "../../types";
import "./AccountList.css";

export interface AccountListProps {
  onSelectAccount: (
    account: Account,
    initialTab?: "signals" | "perimeter" | "history" | "assets" | "ips" | "domains" | "tech"
  ) => void;
  tierFilter?: string | null;
  searchQuery?: string;
  onTierChange?: (tier: string | null) => void;
}

export const AccountList: React.FC<AccountListProps> = ({
  onSelectAccount,
  tierFilter,
  searchQuery,
  onTierChange,
}) => {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [loading, setLoading] = useState(false);
  const [filter, setFilter] = useState<PriorityTier | "all">("all");
  const [skip, setSkip] = useState(0);
  const [total, setTotal] = useState(0);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);
  const limit = 20;
  const isSearching = Boolean(searchQuery?.trim());

  // Keep local filter synced when tierFilter prop changes from parent
  useEffect(() => {
    if (tierFilter === null || tierFilter === "all") {
      setFilter("all");
    } else if (tierFilter) {
      setFilter(tierFilter as PriorityTier);
    }
    setSkip(0);
  }, [tierFilter]);

  // Reset pagination when search query changes
  useEffect(() => {
    setSkip(0);
  }, [searchQuery]);

  // Single data fetching effect with race condition cancellation
  useEffect(() => {
    let isCancelled = false;

    const fetchAccounts = async () => {
      setLoading(true);
      try {
        let items: Account[] = [];
        let totalCount = 0;

        if (searchQuery?.trim()) {
          const result = await api.searchAccounts(searchQuery.trim());
          items = result.results || [];
          totalCount = result.total || 0;
        } else {
          const result = await api.listAccounts(skip, limit, {
            ...(filter !== "all" && { priority_tier: filter }),
          });
          items = result.items || [];
          totalCount = result.total || 0;
        }

        if (!isCancelled) {
          setAccounts(items);
          setTotal(totalCount);
        }
      } catch (err) {
        if (!isCancelled) {
          console.error("Failed to load accounts:", err);
        }
      } finally {
        if (!isCancelled) {
          setLoading(false);
        }
      }
    };

    fetchAccounts();

    return () => {
      isCancelled = true;
    };
  }, [searchQuery, filter, skip]);

  const handleTierFilterChange = (newTier: PriorityTier | "all") => {
    setFilter(newTier);
    setSkip(0);
    if (onTierChange) {
      onTierChange(newTier === "all" ? null : newTier);
    }
  };

  const computeAccountTier = (account: Account): PriorityTier => {
    if (account.priority_tier) return account.priority_tier;
    if (account.latest_score?.priority_tier) {
      return account.latest_score.priority_tier;
    }
    if ((account.critical_signals_count || 0) > 0) return "tier_1_critical";
    if ((account.high_signals_count || 0) >= 2) return "tier_2_high";
    if ((account.high_signals_count || 0) > 0 || (account.total_signals_count || 0) > 0) return "tier_3_medium";

    const hasCrit = account.signals?.some((s) => s.severity === "critical");
    const highCount = account.signals?.filter((s) => s.severity === "high").length || 0;
    if (hasCrit) return "tier_1_critical";
    if (highCount >= 2) return "tier_2_high";
    if (highCount > 0 || (account.signals?.length || 0) > 0) return "tier_3_medium";
    return "tier_4_low";
  };

  const getTierBadgeInfo = (tier: PriorityTier) => {
    switch (tier) {
      case "tier_1_critical":
        return { label: "Tier 1 · Critical", icon: "🚨", className: "tier-badge-critical" };
      case "tier_2_high":
        return { label: "Tier 2 · High", icon: "🔥", className: "tier-badge-high" };
      case "tier_3_medium":
        return { label: "Tier 3 · Medium", icon: "⚡", className: "tier-badge-medium" };
      case "tier_4_low":
      default:
        return { label: "Tier 4 · Low", icon: "🛡️", className: "tier-badge-low" };
    }
  };

  const handleCopy = (e: React.MouseEvent, text: string) => {
    e.stopPropagation();
    navigator.clipboard.writeText(text);
    setCopiedKey(text);
    setTimeout(() => setCopiedKey(null), 1500);
  };

  return (
    <div className="account-list-wrapper">
      {/* List Toolbar & Active Filter Status */}
      {(filter !== "all" || isSearching) && (
        <div className="list-toolbar">
          <div className="active-filter-indicators">
            {filter !== "all" && (
              <span className="active-filter-pill">
                <span>Filter: <strong>{getTierBadgeInfo(filter).label}</strong></span>
                <button
                  className="clear-filter-x-btn"
                  onClick={() => handleTierFilterChange("all")}
                  title="Clear tier filter"
                >
                  ✕
                </button>
              </span>
            )}
            {isSearching && (
              <span className="search-active-pill">
                Search: <strong>"{searchQuery}"</strong>
              </span>
            )}
          </div>

          <div className="toolbar-stats">
            <span className="results-count">
              {total.toLocaleString()} {total === 1 ? "matching account" : "matching accounts"}
            </span>
          </div>
        </div>
      )}

      {/* Main Table Content */}
      {loading ? (
        <div className="table-skeleton-container">
          {[...Array(6)].map((_, i) => (
            <div key={i} className="skeleton-row">
              <div className="skeleton-cell w-domain"></div>
              <div className="skeleton-cell w-tier"></div>
              <div className="skeleton-cell w-signals"></div>
              <div className="skeleton-cell w-score"></div>
              <div className="skeleton-cell w-action"></div>
            </div>
          ))}
        </div>
      ) : accounts.length === 0 ? (
        <div className="empty-state-card">
          <div className="empty-icon">🔍</div>
          <h3 className="empty-title">No matching accounts found</h3>
          <p className="empty-desc">
            Try adjusting your search criteria or clear the current tier filter to view more records.
          </p>
          {(filter !== "all" || isSearching) && (
            <button
              className="empty-reset-btn"
              onClick={() => {
                handleTierFilterChange("all");
              }}
            >
              Reset Filters
            </button>
          )}
        </div>
      ) : (
        <>
          <div className="table-responsive-container">
            <table className="modern-accounts-table">
              <thead>
                <tr>
                  <th className="col-domain">Account / Domain</th>
                  <th className="col-tier">Priority Tier</th>
                  <th className="col-signals">Detected Threats / Signals</th>
                  <th className="col-ai-score">AI Risk Score</th>
                  <th className="col-action">Drilldown</th>
                </tr>
              </thead>
              <tbody>
                {accounts.map((account) => {
                  const tier = computeAccountTier(account);
                  const tierBadge = getTierBadgeInfo(tier);
                  const critSignals = account.critical_signals_count ?? account.signals?.filter((s) => s.severity === "critical").length ?? 0;
                  const highSignals = account.high_signals_count ?? account.signals?.filter((s) => s.severity === "high").length ?? 0;
                  const medSignals = account.medium_signals_count ?? account.signals?.filter((s) => s.severity === "medium").length ?? 0;
                  const lowSignals = account.low_signals_count ?? account.signals?.filter((s) => s.severity === "low").length ?? 0;
                  const totalSignals = account.total_signals_count ?? (critSignals + highSignals + medSignals + lowSignals);
                  const primaryDomain = account.domain || account.domains?.[0] || account.account_key.replace("domain:", "");
                  const domainsList = account.domains || (account.domain ? [account.domain] : []);
                  const extraDomains = Math.max(0, domainsList.length - 1);
                  const aiScoreVal = account.ai_score ?? account.latest_score?.score;
                  const accountVersion = account.version || (account.account_key.includes(":v") ? account.account_key.split(":").pop() : "v1");

                  return (
                    <tr
                      key={account.account_key}
                      className="account-row-item"
                      onClick={() => onSelectAccount(account, "signals")}
                    >
                      {/* 1. Account / Domain */}
                      <td className="cell-domain">
                        <div className="domain-primary-wrap">
                          <span className="domain-globe-icon">🌐</span>
                          <span className="domain-main-text" title={`${primaryDomain} (${accountVersion})`}>
                            {primaryDomain}
                          </span>
                          <span className={`domain-version-badge ${accountVersion}`} title={`Scan Snapshot Version: ${accountVersion}`}>
                            {accountVersion}
                          </span>
                          {account.total_versions && account.total_versions > 1 ? (
                            <span className="domain-multi-versions-badge" title={`${account.total_versions} scan snapshots available in detail view`}>
                              {account.total_versions} versions
                            </span>
                          ) : null}
                          <button
                            className="domain-copy-btn"
                            onClick={(e) => handleCopy(e, primaryDomain)}
                            title="Copy domain"
                          >
                            {copiedKey === primaryDomain ? "✓" : "📋"}
                          </button>
                          {extraDomains > 0 && (
                            <span className="extra-domains-badge" title={domainsList.slice(1).join(", ")}>
                              +{extraDomains}
                            </span>
                          )}
                        </div>
                      </td>

                      {/* 2. Priority Tier */}
                      <td className="cell-tier">
                        <span className={`table-tier-badge ${tierBadge.className}`}>
                          <span className="badge-emoji">{tierBadge.icon}</span>
                          <span>{tierBadge.label}</span>
                        </span>
                      </td>

                      {/* 3. Detected Threats / Signals */}
                      <td
                        className="cell-signals interactive-cell"
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelectAccount(account, "signals");
                        }}
                        title="Click to view full security signal breakdown"
                      >
                        <div className="signals-summary-group">
                          {totalSignals === 0 ? (
                            <span className="threat-zero-pill">🛡️ 0 Threats Detected</span>
                          ) : (
                            <>
                              <span className="threats-total-pill">
                                <strong>{totalSignals}</strong> {totalSignals === 1 ? "Threat" : "Threats"}
                              </span>
                              {critSignals > 0 && (
                                <span className="threat-mini-badge badge-crit" title={`${critSignals} Critical Threats`}>
                                  🚨 {critSignals}
                                </span>
                              )}
                              {highSignals > 0 && (
                                <span className="threat-mini-badge badge-high" title={`${highSignals} High Severity Threats`}>
                                  🔥 {highSignals}
                                </span>
                              )}
                              {medSignals > 0 && critSignals === 0 && highSignals === 0 && (
                                <span className="threat-mini-badge badge-med" title={`${medSignals} Medium Risk Signals`}>
                                  ⚡ {medSignals}
                                </span>
                              )}
                            </>
                          )}
                        </div>
                      </td>

                      {/* 4. AI Risk Score */}
                      <td
                        className="cell-ai-score interactive-cell"
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelectAccount(account, "history");
                        }}
                        title="Click to view AI analysis and version history"
                      >
                        {typeof aiScoreVal === "number" && aiScoreVal > 0 ? (
                          <span
                            className="ai-score-cell-badge"
                            title={`Gemini AI Risk Score: ${aiScoreVal}/100`}
                          >
                            <span className="ai-score-bolt">⚡</span>
                            <strong>{aiScoreVal}</strong>
                            <span className="ai-score-max">/100</span>
                          </span>
                        ) : (
                          <span className="ai-score-unscored-badge" title="Not yet scored with AI">
                            —
                          </span>
                        )}
                      </td>

                      {/* 5. Drilldown */}
                      <td
                        className="cell-action"
                        onClick={(e) => {
                          e.stopPropagation();
                          onSelectAccount(account, "signals");
                        }}
                      >
                        <span className="row-action-link">
                          View Drilldown →
                        </span>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>

          {/* Polished Pagination Footer */}
          <div className="modern-pagination-footer">
            <div className="pagination-range-info">
              Showing <strong>{Math.min(skip + 1, total)}</strong>–
              <strong>{Math.min(skip + limit, total)}</strong> of{" "}
              <strong>{total.toLocaleString()}</strong> accounts
            </div>

            <div className="pagination-controls">
              <button
                className="pag-btn pag-arrow"
                disabled={skip === 0}
                onClick={() => setSkip(Math.max(0, skip - limit))}
                title="Previous page"
              >
                ← Prev
              </button>

              {(() => {
                const currentPage = Math.floor(skip / limit) + 1;
                const totalPages = Math.ceil(total / limit);
                const pages: (number | string)[] = [];
                const maxVisible = 5;

                if (totalPages <= maxVisible) {
                  for (let i = 1; i <= totalPages; i++) pages.push(i);
                } else {
                  pages.push(1);
                  if (currentPage > 3) pages.push("...");

                  for (
                    let i = Math.max(2, currentPage - 1);
                    i <= Math.min(totalPages - 1, currentPage + 1);
                    i++
                  ) {
                    pages.push(i);
                  }

                  if (currentPage < totalPages - 2) pages.push("...");
                  pages.push(totalPages);
                }

                return pages.map((page, idx) =>
                  page === "..." ? (
                    <span key={`ellipsis-${idx}`} className="pag-ellipsis">
                      …
                    </span>
                  ) : (
                    <button
                      key={page}
                      className={`pag-btn pag-num ${currentPage === page ? "active" : ""}`}
                      onClick={() => setSkip((Number(page) - 1) * limit)}
                    >
                      {page}
                    </button>
                  )
                );
              })()}

              <button
                className="pag-btn pag-arrow"
                disabled={skip + limit >= total}
                onClick={() => setSkip(skip + limit)}
                title="Next page"
              >
                Next →
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export default AccountList;

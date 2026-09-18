import React, { useState, useEffect, useCallback, useRef } from "react";
import { api } from "../../api";
import { useAppStore } from "../../store";
import { BackgroundJobSummary, BackgroundJobDetail, JobStatusType, ScannerEngineInfo } from "../../types";
import "./CrawlerAppPage.css";

interface Props {
  onBackToAccounts: () => void;
  onSelectAccount?: (account: any) => void;
}

type ScanDepth = "quick" | "standard" | "deep";
type TabView = "jobs" | "results";
type StatusFilter = "all" | "running" | "completed" | "failed";

const DEFAULT_SCANNERS: ScannerEngineInfo[] = [
  {
    id: "all",
    name: "Comprehensive Security Suite (All Engines)",
    description: "Orchestrates Standard Network Crawler, OWASP ZAP DAST, ProjectDiscovery (Subfinder/HTTPX/Nuclei), and CISA KEV threat feeds simultaneously.",
    badge: "Recommended · Full Depth",
    icon: "🚀",
  },
  {
    id: "standard",
    name: "Standard Network & Banner Crawler",
    description: "Multi-threaded DNS resolution, common subdomains, port probing, and cloud provider fingerprinting.",
    badge: "Fast Network Recon",
    icon: "🌐",
  },
  {
    id: "owasp_zap",
    name: "OWASP ZAP DAST Vulnerability Scanner",
    description: "OWASP Top 10 Web App Security Auditor: CSP, HSTS, CORS, Clickjacking, Cookie Flags, and Sensitive Exposure.",
    badge: "DAST & Web Audit",
    icon: "🛡️",
  },
  {
    id: "projectdiscovery",
    name: "ProjectDiscovery Suite (Subfinder, HTTPX, Naabu, Nuclei)",
    description: "Subdomain discovery, fast multi-port probing, technology fingerprinting, and Nuclei vulnerability template scanning.",
    badge: "Deep Recon",
    icon: "⚡",
  },
  {
    id: "cisa_kev",
    name: "CISA KEV & Exploited CVE Threat Feed",
    description: "Correlates perimeter banners and technologies against the official CISA Known Exploited Vulnerabilities catalog.",
    badge: "Threat Intel",
    icon: "🚨",
  },
];

export const CrawlerAppPage: React.FC<Props> = ({ onBackToAccounts, onSelectAccount }) => {
  const { openProfileModal, currentUser } = useAppStore();

  const [pipelineName, setPipelineName] = useState<string>("");
  const [domainsInput, setDomainsInput] = useState<string>("stripe.com, shopify.com");
  const [scanDepth, setScanDepth] = useState<ScanDepth>("standard");
  const [selectedScanner, setSelectedScanner] = useState<string>("all");
  const [availableScanners, setAvailableScanners] = useState<ScannerEngineInfo[]>(DEFAULT_SCANNERS);
  const [enableSubdomains, setEnableSubdomains] = useState<boolean>(true);
  const [saveToDb, setSaveToDb] = useState<boolean>(true);
  const [customPortsInput, setCustomPortsInput] = useState<string>("");
  const [showOptionsDropdown, setShowOptionsDropdown] = useState<boolean>(false);

  const [submitting, setSubmitting] = useState<boolean>(false);
  const [activeNotification, setActiveNotification] = useState<{ message: string; type: "info" | "success" | "error"; jobId?: string } | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const [jobs, setJobs] = useState<BackgroundJobSummary[]>([]);
  const [loadingJobs, setLoadingJobs] = useState<boolean>(false);
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [selectedJobDetail, setSelectedJobDetail] = useState<BackgroundJobDetail | null>(null);
  const [loadingDetail, setLoadingDetail] = useState<boolean>(false);
  const [activeTab, setActiveTab] = useState<TabView>("jobs");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [retryingJobId, setRetryingJobId] = useState<string | null>(null);

  const optionsDropdownRef = useRef<HTMLDivElement | null>(null);

  const fetchJobs = useCallback(async (silent = false) => {
    if (!silent) setLoadingJobs(true);
    try {
      const resp = await api.listCrawlerJobs({ limit: 50 });
      if (resp && resp.items) {
        setJobs(resp.items);
      }
    } catch (err: any) {
      if (!silent) {
        setErrorMsg(err.response?.data?.detail || err.message || "Failed to fetch crawler jobs");
      }
    } finally {
      if (!silent) setLoadingJobs(false);
    }
  }, []);

  useEffect(() => {
    fetchJobs();
    api.getAvailableScanners().then((res) => {
      if (res && res.scanners && res.scanners.length > 0) {
        setAvailableScanners(res.scanners);
      }
    }).catch(() => {});
  }, [fetchJobs]);

  // Click outside listener for options popover
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (optionsDropdownRef.current && !optionsDropdownRef.current.contains(event.target as Node)) {
        setShowOptionsDropdown(false);
      }
    };
    if (showOptionsDropdown) {
      document.addEventListener("mousedown", handleClickOutside);
    }
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [showOptionsDropdown]);

  const fetchJobDetail = async (jobId: string, silent = false) => {
    if (!silent) setLoadingDetail(true);
    try {
      const detail = await api.getCrawlerJob(jobId);
      setSelectedJobDetail(detail);
      setSelectedJobId(jobId);
      setActiveTab("results");
    } catch (err: any) {
      if (!silent) {
        setErrorMsg(`Failed to load job details: ${err.message}`);
      }
    } finally {
      if (!silent) setLoadingDetail(false);
    }
  };

  const handleAddSample = (domain: string) => {
    const list = domainsInput.trim() ? domainsInput.trim().split(/[\n,]+/).map((d) => d.trim()).filter(Boolean) : [];
    if (!list.includes(domain)) {
      list.push(domain);
      setDomainsInput(list.join(", "));
    }
  };

  const handleExecuteCrawler = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);
    setShowOptionsDropdown(false);

    const domains = domainsInput
      .split(/[\n,]+/)
      .map((d) => d.trim().replace(/^https?:\/\//i, "").replace(/\/.*$/, ""))
      .filter((d) => d.length > 0);

    if (domains.length === 0) {
      setErrorMsg("Please provide at least one valid target domain to crawl.");
      return;
    }

    const ports = customPortsInput
      .split(/[\s,]+/)
      .map((p) => parseInt(p.trim(), 10))
      .filter((p) => !isNaN(p) && p > 0 && p <= 65535);

    setSubmitting(true);

    try {
      const resp = await api.submitCrawlerJob({
        pipeline_name: pipelineName.trim() || undefined,
        domains,
        scan_depth: scanDepth,
        scanner_type: selectedScanner,
        enable_subdomains: enableSubdomains,
        custom_ports: ports.length > 0 ? ports : undefined,
        save_to_database: saveToDb,
      });

      setActiveNotification({
        message: resp.message || `Crawl job submitted (${resp.job_id.substring(0, 16)}...). Recon running in background.`,
        type: "success",
        jobId: resp.job_id,
      });

      await fetchJobs();
      setActiveTab("jobs");
    } catch (err: any) {
      const detail = err.response?.data?.detail || err.message || "Failed to submit web crawler background job";
      setErrorMsg(detail);
    } finally {
      setSubmitting(false);
    }
  };

  const handleScoreAndProspect = async (res: any) => {
    const accKey = res.account_key || res.account?.account_key || `domain:${res.domain}`;
    try {
      const existing = await api.getAccount(accKey);
      if (existing) {
        onSelectAccount?.(existing);
        return;
      }
    } catch {
      // If not yet saved in DB, fallback to crawled account payload
    }
    if (res.account) {
      onSelectAccount?.(res.account);
    }
  };

  const handleRetryJob = async (jobId: string, e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    setRetryingJobId(jobId);
    try {
      const resp = await api.retryCrawlerJob(jobId);
      setActiveNotification({
        message: resp.message || `Job retry queued (${resp.job_id})`,
        type: "info",
        jobId: resp.job_id,
      });
      await fetchJobs();
    } catch (err: any) {
      setErrorMsg(`Failed to retry job: ${err.message}`);
    } finally {
      setRetryingJobId(null);
    }
  };

  const formatTimestamp = (ts?: string | null) => {
    if (!ts) return "—";
    try {
      const d = new Date(ts);
      return d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
    } catch {
      return ts;
    }
  };

  const formatDuration = (ms?: number | null) => {
    if (!ms && ms !== 0) return "—";
    if (ms < 1000) return `${ms}ms`;
    return `${(ms / 1000).toFixed(1)}s`;
  };

  const renderStatusBadge = (status: JobStatusType, percent: number) => {
    switch (status) {
      case "queued":
        return <span className="job-badge queued">⏳ Queued</span>;
      case "running":
        return (
          <span className="job-badge running">
            <span className="badge-pulse" />
            <span>Scanning ({percent}%)</span>
          </span>
        );
      case "completed":
        return <span className="job-badge completed">✓ Completed</span>;
      case "failed":
        return <span className="job-badge failed">✕ Failed</span>;
      case "cancelled":
        return <span className="job-badge cancelled">⊘ Cancelled</span>;
      default:
        return <span className="job-badge">{status}</span>;
    }
  };

  const filteredJobs = jobs.filter((j) => {
    if (statusFilter === "running") return j.status === "running" || j.status === "queued";
    if (statusFilter === "completed") return j.status === "completed";
    if (statusFilter === "failed") return j.status === "failed" || j.status === "cancelled";
    return true;
  });

  const parsedDomainsCount = domainsInput.split(/[\n,]+/).filter((d) => d.trim().length > 0).length;

  return (
    <div className="crawler-page-container">
      {/* Sleek Top Header */}
      <div className="crawler-topbar">
        <div className="topbar-left">
          <button className="btn-back-nav" onClick={onBackToAccounts}>
            <span>←</span>
            <span>Accounts</span>
          </button>
          <span className="topbar-divider" />
          <div className="topbar-title-wrap">
            <h2 className="topbar-title">Perimeter Recon &amp; Attack Surface Crawler</h2>
            <span className="engine-status-pill">● Non-Blocking Engine</span>
          </div>
        </div>

        <div className="topbar-right">
          <div className="quick-presets-group">
            <span className="presets-label">Quick Samples:</span>
            <button type="button" className="preset-pill" onClick={() => handleAddSample("github.com")}>+ GitHub</button>
            <button type="button" className="preset-pill" onClick={() => handleAddSample("stripe.com")}>+ Stripe</button>
            <button type="button" className="preset-pill" onClick={() => handleAddSample("cloudflare.com")}>+ Cloudflare</button>
            <button type="button" className="preset-pill" onClick={() => handleAddSample("medium.com")}>+ Medium</button>
          </div>

          <div className="key-status-wrap">
            {currentUser?.has_api_key ? (
              <span className="key-badge active" onClick={openProfileModal} title="Personal Key Configured">
                ✓ Personal Key Active
              </span>
            ) : (
              <span className="key-badge" onClick={openProfileModal} title="Configure Gemini API Key">
                Using Server Default Key ↗
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Floating Notification Toast */}
      {activeNotification && (
        <div className={`recon-toast ${activeNotification.type}`}>
          <div className="toast-content">
            <span className="toast-emoji">
              {activeNotification.type === "success" ? "🚀" : activeNotification.type === "info" ? "ℹ️" : "⚠️"}
            </span>
            <span className="toast-text">{activeNotification.message}</span>
          </div>
          <div className="toast-btns">
            {activeNotification.jobId && (
              <button
                type="button"
                className="btn-toast-inspect"
                onClick={() => fetchJobDetail(activeNotification.jobId!)}
              >
                Inspect Results ➔
              </button>
            )}
            <button
              type="button"
              className="btn-toast-close"
              onClick={() => setActiveNotification(null)}
            >
              ✕
            </button>
          </div>
        </div>
      )}

      {/* Top Card: Scan Launchpad Command Card (2 Rows) */}
      <div className="recon-launchpad-card">
        <form onSubmit={handleExecuteCrawler} className="launchpad-form">
          {/* ROW 1: Pipeline Name & Target Perimeters */}
          <div className="launchpad-row-top">
            <div className="pipeline-input-box">
              <div className="scan-input-prefix">
                <span className="target-icon">🏷️</span>
                <span className="target-label">Pipeline Name</span>
              </div>
              <input
                type="text"
                className="scan-text-input pipeline-text-input"
                value={pipelineName}
                onChange={(e) => setPipelineName(e.target.value)}
                placeholder="e.g. Q3 Fintech Perimeter Recon"
                disabled={submitting}
              />
            </div>

            <div className="scan-input-box">
              <div className="scan-input-prefix">
                <span className="target-icon">🎯</span>
                <span className="target-label">Target Perimeters</span>
                <span className="target-badge">{parsedDomainsCount} Domain{parsedDomainsCount !== 1 ? "s" : ""}</span>
              </div>
              <input
                type="text"
                className="scan-text-input"
                value={domainsInput}
                onChange={(e) => setDomainsInput(e.target.value)}
                placeholder="stripe.com, shopify.com, medium.com..."
                disabled={submitting}
                required
              />
            </div>
          </div>

          {/* ROW 2: Security Scanner Engine & Tooling Selector Grid */}
          <div className="scanner-engine-selector-section">
            <div className="scanner-section-header">
              <span className="scanner-section-label">🛠️ Select Security Scanner Engines &amp; Threat Intelligence:</span>
              <span className="scanner-active-tag">
                Selected: <strong>{availableScanners.find(s => s.id === selectedScanner)?.name || "Comprehensive Security Suite"}</strong>
              </span>
            </div>

            <div className="scanner-options-grid">
              {availableScanners.map((sc) => {
                const isSelected = selectedScanner === sc.id;
                return (
                  <div
                    key={sc.id}
                    className={`scanner-option-card ${isSelected ? "selected" : ""}`}
                    onClick={() => setSelectedScanner(sc.id)}
                  >
                    <div className="scanner-card-top">
                      <span className="scanner-card-icon">{sc.icon}</span>
                      <span className="scanner-card-badge">{sc.badge}</span>
                    </div>
                    <div className="scanner-card-title">{sc.name}</div>
                    <div className="scanner-card-desc">{sc.description}</div>
                  </div>
                );
              })}
            </div>
          </div>

          {/* ROW 3: Scan Depth, Options & Launch Button */}
          <div className="launchpad-row-bottom">
            <div className="launchpad-bottom-left">
              {/* Scan Depth Selector */}
              <div className="scan-depth-pill-group">
                <button
                  type="button"
                  className={`depth-pill ${scanDepth === "quick" ? "active" : ""}`}
                  onClick={() => setScanDepth("quick")}
                  title="Quick DNS & Standard Web Ports (80, 443)"
                >
                  <span>⚡ Quick</span>
                </button>
                <button
                  type="button"
                  className={`depth-pill ${scanDepth === "standard" ? "active" : ""}`}
                  onClick={() => setScanDepth("standard")}
                  title="Subdomains + Top 6 Ports"
                >
                  <span>🛡️ Standard</span>
                </button>
                <button
                  type="button"
                  className={`depth-pill ${scanDepth === "deep" ? "active" : ""}`}
                  onClick={() => setScanDepth("deep")}
                  title="Deep Subdomains + All Ports Range"
                >
                  <span>🔥 Deep Sweep</span>
                </button>
              </div>

              {/* Options Dropdown Popover */}
              <div className="options-dropdown-container" ref={optionsDropdownRef}>
                <button
                  type="button"
                  className={`btn-options-toggle ${showOptionsDropdown ? "active" : ""}`}
                  onClick={() => setShowOptionsDropdown(!showOptionsDropdown)}
                >
                  <span>⚙️ Discovery Options</span>
                  <span className="chevron-icon">{showOptionsDropdown ? "▲" : "▼"}</span>
                </button>

                {showOptionsDropdown && (
                  <div className="options-popover-menu">
                    <div className="popover-header">Discovery &amp; Ingestion Options</div>
                    <label className="popover-checkbox-row">
                      <input
                        type="checkbox"
                        checked={enableSubdomains}
                        onChange={(e) => setEnableSubdomains(e.target.checked)}
                        disabled={submitting}
                      />
                      <span>Discover Subdomains (api, app, auth, mail...)</span>
                    </label>

                    <label className="popover-checkbox-row">
                      <input
                        type="checkbox"
                        checked={saveToDb}
                        onChange={(e) => setSaveToDb(e.target.checked)}
                        disabled={submitting}
                      />
                      <span>Save Discovered Accounts to Database</span>
                    </label>

                    <div className="popover-port-range">
                      <span className="port-range-label">Custom Port Probes:</span>
                      <input
                        type="text"
                        className="port-range-input"
                        value={customPortsInput}
                        onChange={(e) => setCustomPortsInput(e.target.value)}
                        placeholder="80, 443, 8080, 8443..."
                        disabled={submitting}
                      />
                    </div>
                  </div>
                )}
              </div>
            </div>

            <div className="launchpad-bottom-right">
              {/* Launch Action Button */}
              <button
                type="submit"
                className="btn-launch-row"
                disabled={submitting || !domainsInput.trim()}
              >
                {submitting ? (
                  <>
                    <span className="scan-spinner" />
                    <span>Launching Pipeline...</span>
                  </>
                ) : (
                  <>
                    <span>🚀 Launch Security Recon</span>
                  </>
                )}
              </button>
            </div>
          </div>
        </form>

        {/* Error Alert if any */}
        {errorMsg && (
          <div className="recon-row-error">
            <span>⚠️ {errorMsg}</span>
          </div>
        )}
      </div>

      {/* Bottom Card: Background Jobs & Results Table Card */}
      <div className="recon-main-card">
        {/* ROW 2: HEADER (When on Jobs list) */}
        {activeTab === "jobs" && (
          <div className="main-card-header">
            <div className="queue-header-left">
              <h3 className="queue-section-title">
                <span>📋</span>
                <span>Background Jobs Queue</span>
                <span className="tab-pill-badge">{jobs.length}</span>
              </h3>
            </div>

            <div className="header-actions-right">
              <div className="status-filter-pills">
                <button
                  type="button"
                  className={`filter-pill ${statusFilter === "all" ? "active" : ""}`}
                  onClick={() => setStatusFilter("all")}
                >
                  All ({jobs.length})
                </button>
                <button
                  type="button"
                  className={`filter-pill ${statusFilter === "running" ? "active" : ""}`}
                  onClick={() => setStatusFilter("running")}
                >
                  Running ({jobs.filter((j) => j.status === "running" || j.status === "queued").length})
                </button>
                <button
                  type="button"
                  className={`filter-pill ${statusFilter === "completed" ? "active" : ""}`}
                  onClick={() => setStatusFilter("completed")}
                >
                  Completed ({jobs.filter((j) => j.status === "completed").length})
                </button>
                <button
                  type="button"
                  className={`filter-pill ${statusFilter === "failed" ? "active" : ""}`}
                  onClick={() => setStatusFilter("failed")}
                >
                  Failed ({jobs.filter((j) => j.status === "failed" || j.status === "cancelled").length})
                </button>
              </div>

              <button
                type="button"
                className="btn-sync-jobs"
                onClick={() => fetchJobs()}
                disabled={loadingJobs}
                title="Refresh jobs status"
              >
                <span className={loadingJobs ? "rotating" : ""}>🔄</span>
                <span>Sync</span>
              </button>
            </div>
          </div>
        )}

        {/* TAB 1: BACKGROUND JOBS QUEUE TABLE */}
        {activeTab === "jobs" && (
          <div className="tab-body-wrapper">
            {filteredJobs.length === 0 && !loadingJobs && (
              <div className="recon-empty-state">
                <span className="empty-state-icon">🌐</span>
                <h4>No Crawl Tasks Found</h4>
                <p>Enter target domains in the top scan bar and click "Launch Scan" to begin reconnaissance.</p>
              </div>
            )}

            {filteredJobs.length > 0 && (
              <div className="recon-table-wrapper">
                <table className="recon-table">
                  <thead>
                    <tr>
                      <th>Target Perimeters</th>
                      <th>Status</th>
                      <th>Progress</th>
                      <th>Assets / Signals</th>
                      <th>Duration</th>
                      <th>Created</th>
                      <th className="th-actions">Actions</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredJobs.map((job) => {
                      const isSelected = selectedJobId === job.job_id;
                      return (
                        <tr
                          key={job.job_id}
                          className={`recon-row ${isSelected ? "selected-row" : ""}`}
                          onClick={() => fetchJobDetail(job.job_id)}
                        >
                          <td className="col-target">
                            <div className="target-title-wrap">
                              <span className="target-globe-icon">🚀</span>
                              <span className="target-title" title={job.title}>
                                {job.title}
                              </span>
                            </div>
                            <div className="target-meta-line">
                              {job.metadata?.domains_count ? (
                                <span className="job-domain-count-badge">
                                  🌐 {job.metadata.domains_count} domain{job.metadata.domains_count !== 1 ? "s" : ""}
                                </span>
                              ) : null}
                              <span className="job-hash">ID: {job.job_id.substring(0, 8)}...</span>
                              {job.metadata?.scan_depth && (
                                <span className="job-depth-badge">{job.metadata.scan_depth}</span>
                              )}
                            </div>
                          </td>

                          <td className="col-status">
                            {renderStatusBadge(job.status, job.progress_percent)}
                            {job.error_message && (
                              <div className="error-preview-line" title={job.error_message}>
                                {job.error_message.substring(0, 30)}...
                              </div>
                            )}
                          </td>

                          <td className="col-progress">
                            <div className="progress-track">
                              <div
                                className={`progress-fill ${job.status}`}
                                style={{ width: `${job.progress_percent}%` }}
                              />
                            </div>
                            <span className="progress-label">
                              {job.progress_current}/{job.progress_total} ({job.progress_percent}%)
                            </span>
                          </td>

                          <td className="col-metrics">
                            {job.status === "completed" ? (
                              <div className="metrics-pill-group">
                                <span className="metric-pill assets">
                                  🏢 {job.metadata?.assets_discovered_count || 0}
                                </span>
                                <span className={`metric-pill signals ${job.metadata?.signals_detected_count ? "has-signals" : ""}`}>
                                  🛡️ {job.metadata?.signals_detected_count || 0}
                                </span>
                              </div>
                            ) : (
                              <span className="muted-dash">—</span>
                            )}
                          </td>

                          <td className="col-duration">
                            {formatDuration(job.duration_ms)}
                          </td>

                          <td className="col-time">
                            {formatTimestamp(job.created_at)}
                          </td>

                          <td className="col-actions" onClick={(e) => e.stopPropagation()}>
                            <div className="action-buttons-wrap">
                              <button
                                type="button"
                                className="btn-table-action inspect"
                                onClick={() => fetchJobDetail(job.job_id)}
                                title="Inspect Discovery Results"
                              >
                                Inspect
                              </button>

                              {(job.status === "failed" || job.status === "cancelled") && (
                                <button
                                  type="button"
                                  className="btn-table-action retry"
                                  onClick={(e) => handleRetryJob(job.job_id, e)}
                                  disabled={retryingJobId === job.job_id}
                                  title="Retry Task"
                                >
                                  {retryingJobId === job.job_id ? "..." : "Retry"}
                                </button>
                              )}
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        )}

        {/* TAB 2: DISCOVERY RESULTS DOSSIER */}
        {activeTab === "results" && (
          <div className="tab-body-wrapper dossier-wrapper">
            {/* Top Back Navigation Bar */}
            <div className="dossier-back-nav-bar">
              <button
                type="button"
                className="btn-back-to-jobs"
                onClick={() => setActiveTab("jobs")}
              >
                <span className="back-arrow">←</span>
                <span>Back to Background Jobs Queue</span>
              </button>
              <div className="dossier-nav-right">
                <button
                  type="button"
                  className="btn-sync-jobs"
                  onClick={() => selectedJobId && fetchJobDetail(selectedJobId)}
                  disabled={loadingDetail}
                  title="Refresh discovery details"
                >
                  <span className={loadingDetail ? "rotating" : ""}>🔄</span>
                  <span>Refresh Job</span>
                </button>
              </div>
            </div>

            {loadingDetail && (
              <div className="recon-loading-state">
                <span className="scan-spinner large" />
                <p>Loading discovery telemetry &amp; security posture...</p>
              </div>
            )}

            {!loadingDetail && !selectedJobDetail && (
              <div className="recon-empty-state">
                <span className="empty-state-icon">🔍</span>
                <h4>No Crawl Task Selected</h4>
                <p>Select any crawl task from the jobs queue table to inspect discovered attack surfaces.</p>
                <button
                  type="button"
                  className="btn-back-to-jobs"
                  onClick={() => setActiveTab("jobs")}
                  style={{ marginTop: "12px" }}
                >
                  ← Return to Jobs Queue
                </button>
              </div>
            )}

            {!loadingDetail && selectedJobDetail && (
              <div className="dossier-container">
                {/* Executive Header Banner */}
                <div className="dossier-hero-bar">
                  <div className="dossier-hero-left">
                    <div className="dossier-title-row">
                      <span className="dossier-globe">🌐</span>
                      <div>
                        <h4>{selectedJobDetail.title}</h4>
                        <span className="dossier-trace-id">
                          Job ID: {selectedJobDetail.job_id} · Trace: {selectedJobDetail.trace_id || "trc_auto"}
                        </span>
                      </div>
                    </div>
                  </div>

                  <div className="dossier-hero-right">
                    {renderStatusBadge(selectedJobDetail.status, selectedJobDetail.progress_percent)}
                    {(selectedJobDetail.status === "failed" || selectedJobDetail.status === "cancelled") && (
                      <button
                        type="button"
                        className="btn-dossier-retry"
                        onClick={() => handleRetryJob(selectedJobDetail.job_id)}
                        disabled={retryingJobId === selectedJobDetail.job_id}
                      >
                        🔄 Retry Task
                      </button>
                    )}
                  </div>
                </div>

                {/* High-level KPI Metric Cards */}
                <div className="dossier-kpi-grid">
                  <div className="kpi-card">
                    <span className="kpi-val">{selectedJobDetail.metadata?.domains_count || selectedJobDetail.payload?.domains?.length || 1}</span>
                    <span className="kpi-tag">Domains Crawled</span>
                  </div>
                  <div className="kpi-card">
                    <span className="kpi-val">{selectedJobDetail.metadata?.assets_discovered_count || 0}</span>
                    <span className="kpi-tag">Assets Discovered</span>
                  </div>
                  <div className="kpi-card">
                    <span className="kpi-val text-signals">{selectedJobDetail.metadata?.signals_detected_count || 0}</span>
                    <span className="kpi-tag">Security Signals</span>
                  </div>
                  <div className="kpi-card">
                    <span className="kpi-val">{formatDuration(selectedJobDetail.duration_ms)}</span>
                    <span className="kpi-tag">Scan Duration</span>
                  </div>
                </div>

                {selectedJobDetail.error_message && (
                  <div className="dossier-error-banner">
                    <strong>Execution Error: </strong>
                    <span>{selectedJobDetail.error_message}</span>
                  </div>
                )}

                {/* Discovered Perimeters List */}
                {selectedJobDetail.results && selectedJobDetail.results.length > 0 ? (
                  <div className="discovered-domains-feed">
                    {selectedJobDetail.results.map((res: any, i: number) => (
                      <div key={i} className="domain-recon-card">
                        <div className="domain-card-header">
                          <div className="domain-card-name">
                            <span className="sub-globe">🌐</span>
                            <h5>{res.domain}</h5>
                            {res.version && <span className="version-badge-pill">{res.version}</span>}
                            {res.scanner_type && (
                              <span className="scanner-badge-pill">
                                {res.scanner_type === "all" ? "🚀 FULL SUITE" : `⚙️ ${res.scanner_type.toUpperCase()}`}
                              </span>
                            )}
                            <span className="domain-latency-pill">{res.elapsed_ms}ms</span>
                          </div>

                          {(res.account || res.domain) && (
                            <button
                              type="button"
                              className="btn-score-prospect"
                              onClick={() => handleScoreAndProspect(res)}
                            >
                              <span>⚡ Score &amp; Prospect Account</span>
                              <span>➔</span>
                            </button>
                          )}
                        </div>

                        {res.error ? (
                          <div className="domain-card-error">
                            <span>⚠️ {res.error}</span>
                          </div>
                        ) : (
                          <div className="domain-card-body">
                            {/* Summary Counters */}
                            <div className="domain-counters-row">
                              <div className="counter-pill">
                                <span>Assets:</span>
                                <strong>{res.assets_count}</strong>
                              </div>
                              <div className="counter-pill">
                                <span>IPs:</span>
                                <strong>{res.ips_count}</strong>
                              </div>
                              <div className="counter-pill">
                                <span>Subdomains:</span>
                                <strong>{res.discovered_hosts?.length || 1}</strong>
                              </div>
                              <div className="counter-pill">
                                <span>Threat Signals:</span>
                                <strong className={res.signals_detected_count > 0 ? "text-danger" : "text-safe"}>
                                  {res.signals_detected_count}
                                </strong>
                              </div>
                              {res.vulnerabilities_count > 0 && (
                                <div className="counter-pill vuln-pill">
                                  <span>CVEs / Audits:</span>
                                  <strong>{res.vulnerabilities_count}</strong>
                                </div>
                              )}
                            </div>

                            {/* Tech & Hosts */}
                            <div className="domain-details-grid">
                              <div className="sub-detail-col">
                                <span className="sub-detail-title">Hostnames &amp; Subdomains</span>
                                <div className="pills-flow">
                                  {res.discovered_hosts?.map((h: string, idx: number) => (
                                    <span key={idx} className="sub-pill host">{h}</span>
                                  ))}
                                </div>
                              </div>

                              <div className="sub-detail-col">
                                <span className="sub-detail-title">Technologies &amp; Cloud</span>
                                <div className="pills-flow">
                                  {res.technologies?.map((t: string, idx: number) => (
                                    <span key={idx} className="sub-pill tech">{t}</span>
                                  ))}
                                  {res.cloud_providers?.map((c: string, idx: number) => (
                                    <span key={idx} className="sub-pill cloud">{c}</span>
                                  ))}
                                  {(!res.technologies?.length && !res.cloud_providers?.length) && (
                                    <span className="muted-info">Standard Web Infrastructure</span>
                                  )}
                                </div>
                              </div>
                            </div>

                            {/* Vulnerabilities Section */}
                            {res.vulnerabilities && res.vulnerabilities.length > 0 && (
                              <div className="domain-signals-section">
                                <span className="signals-header-title">🛡️ Identified Vulnerabilities &amp; DAST Audits ({res.vulnerabilities.length}):</span>
                                <div className="signals-pills-flow">
                                  {res.vulnerabilities.map((v: any, idx: number) => (
                                    <span key={idx} className={`signal-tag ${v.severity?.toLowerCase() || "high"}`}>
                                      <span className="sev-dot" />
                                      <span><strong>[{v.id || "VULN"}]</strong> {v.name} {v.severity ? `(${v.severity})` : ""}</span>
                                    </span>
                                  ))}
                                </div>
                              </div>
                            )}

                            {/* Security Signals */}
                            {res.signals && res.signals.length > 0 && (
                              <div className="domain-signals-section">
                                <span className="signals-header-title">Detected Threat Signals ({res.signals.length}):</span>
                                <div className="signals-pills-flow">
                                  {res.signals.map((s: any, idx: number) => (
                                    <span key={idx} className={`signal-tag ${s.severity || "medium"}`}>
                                      <span className="sev-dot" />
                                      <span>[{(s.severity || "info").toUpperCase()}] {s.name?.replace(/_/g, " ")}</span>
                                    </span>
                                  ))}
                                </div>
                              </div>
                            )}
                          </div>
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  selectedJobDetail.status === "running" ? (
                    <div className="scan-active-placeholder">
                      <span className="scan-spinner large" />
                      <h4>Scan in Progress...</h4>
                      <p>Crawling target perimeters in background. Discovered assets will appear here automatically.</p>
                    </div>
                  ) : (
                    <div className="recon-empty-state">
                      <span className="empty-state-icon">📊</span>
                      <h4>No discovery payload recorded</h4>
                    </div>
                  )
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
};

export default CrawlerAppPage;

import React, { useState, useMemo, useEffect } from "react";
import { api } from "../../api";
import { Account, AccountScore, ScoreHistoryItem, AccountVersionSummary } from "../../types";
import { useAppStore } from "../../store";
import "./AccountDetail.css";

interface Props {
  account: Account;
  initialTab?: "signals" | "perimeter" | "history" | "assets" | "ips" | "domains" | "tech";
  onTabChange?: (tab: "signals" | "perimeter" | "history") => void;
  onVersionChange?: (version: string) => Promise<void> | void;
}

interface PerimeterEndpoint {
  id: string;
  hostname: string | null;
  ip: string | null;
  ports: number[];
  technologies: string[];
  isSubdomain: boolean;
  isSensitive: boolean;
  cloudProvider?: string | null;
}

const COMMON_PORT_NAMES: Record<number, string> = {
  21: "FTP",
  22: "SSH",
  23: "Telnet",
  25: "SMTP",
  53: "DNS",
  80: "HTTP",
  110: "POP3",
  143: "IMAP",
  443: "HTTPS",
  445: "SMB",
  1433: "MSSQL",
  1521: "Oracle",
  3306: "MySQL",
  3389: "RDP",
  5432: "PostgreSQL",
  5985: "WinRM-HTTP",
  5986: "WinRM-HTTPS",
  6379: "Redis",
  8000: "HTTP-Dev",
  8080: "HTTP-Alt",
  8443: "HTTPS-Alt",
  8888: "HTTP-Proxy",
  9000: "SonarQube/PHP",
  9200: "Elasticsearch",
  27017: "MongoDB",
};

const HIGH_RISK_PORTS = new Set([21, 22, 23, 445, 1433, 1521, 3306, 3389, 5432, 5985, 5986, 6379, 27017]);

const SIGNAL_METADATA: Record<string, { label: string; icon: string; description: string }> = {
  ransomware_associated_vulnerability: {
    label: "Ransomware Campaign Vulnerability",
    icon: "☣️",
    description: "Active weaponization in documented ransomware campaigns.",
  },
  kev_vulnerability: {
    label: "CISA Known Exploited Vulnerability (KEV)",
    icon: "🚨",
    description: "Listed on CISA KEV with verified in-the-wild exploitation.",
  },
  high_severity_vulnerability: {
    label: "High / Critical Severity CVE",
    icon: "🔥",
    description: "Elevated CVSS score exposing perimeter to remote compromise.",
  },
  high_exploitation_probability: {
    label: "High Exploitation Probability (EPSS)",
    icon: "⚡",
    description: "Statistically elevated probability of weaponization by threat actors.",
  },
  eol_product: {
    label: "End-of-Life (EOL) Software / OS",
    icon: "⏳",
    description: "Unsupported software no longer receiving security patches.",
  },
  multiple_vulnerabilities: {
    label: "Multiple Vulnerability Cluster",
    icon: "⚠️",
    description: "High concentration of CVEs on a single exposed host.",
  },
  non_standard_exposed_port: {
    label: "Non-Standard Exposed Port",
    icon: "🌐",
    description: "Service running on non-default exposed perimeter port.",
  },
};

const SENSITIVE_SUBDOMAIN_PATTERNS = [
  "admin", "portal", "vpn", "auth", "sso", "login", "api", "dev", "test", "stage", "git", "jenkins", "vault", "corp", "internal"
];

const normalizeTab = (tab?: string): "signals" | "perimeter" | "history" => {
  if (tab === "perimeter" || tab === "assets" || tab === "ips" || tab === "domains" || tab === "tech") {
    return "perimeter";
  }
  if (tab === "history" || tab === "intel") {
    return "history";
  }
  return "signals";
};

export const AccountDetail: React.FC<Props> = ({ account, initialTab, onTabChange, onVersionChange }) => {
  // Navigation State (Streamlined to 3 Purpose-Built Tabs)
  const [activeTab, setActiveTab] = useState<"signals" | "perimeter" | "history">(() => normalizeTab(initialTab));

  const handleTabChange = (newTab: "signals" | "perimeter" | "history") => {
    setActiveTab(newTab);
    onTabChange?.(newTab);
  };

  useEffect(() => {
    if (initialTab) {
      setActiveTab(normalizeTab(initialTab));
    }
  }, [initialTab]);

  // AI Score State & Version History
  const [score, setScore] = useState<AccountScore | null>(null);
  const [scoreHistory, setScoreHistory] = useState<ScoreHistoryItem[]>([]);
  const [inspectingHistoricalVersion, setInspectingHistoricalVersion] = useState<ScoreHistoryItem | null>(null);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const [copiedEntity, setCopiedEntity] = useState<string | null>(null);
  const [expandedSignalIdx, setExpandedSignalIdx] = useState<number | null>(null);

  // Tab 1: Signals Filters & State
  const [signalSeverityFilter, setSignalSeverityFilter] = useState<string>("all");
  const [signalSearch, setSignalSearch] = useState<string>("");
  const [signalPage, setSignalPage] = useState<number>(1);
  const signalPageSize = 12;

  // Tab 2: Perimeter Inventory Filters & State
  const [perimeterSearch, setPerimeterSearch] = useState<string>("");
  const [perimeterFilter, setPerimeterFilter] = useState<"all" | "subdomains" | "sensitive" | "risky_ports">("all");
  const [perimeterPage, setPerimeterPage] = useState<number>(1);
  const perimeterPageSize = 25;

  const { addScore, scores, currentUser, openAuthModal, openProfileModal, scoreHistoryCache, cacheScoreHistory } = useAppStore();
  const cachedScore = scores.get(account.account_key);
  const [availableVersions, setAvailableVersions] = useState<AccountVersionSummary[]>(account.available_versions || []);

  useEffect(() => {
    if (account.available_versions && account.available_versions.length > 0) {
      setAvailableVersions(account.available_versions);
    } else {
      api.getAccountVersions(account.account_key)
        .then((res) => {
          if (Array.isArray(res) && res.length > 0) {
            setAvailableVersions(res);
          }
        })
        .catch((err) => {
          console.error("Failed to load versions in AccountDetail:", err);
        });
    }
  }, [account.account_key, account.available_versions]);

  useEffect(() => {
    if (cachedScore) {
      setScore(cachedScore);
    } else if (account.latest_score) {
      setScore({
        account_key: account.account_key,
        account,
        score: account.latest_score.score,
        score_rationale: account.latest_score.score_rationale || undefined,
        priority_tier: account.latest_score.priority_tier,
        key_risks: account.latest_score.key_risks || [],
        suggested_outreach: account.latest_score.suggested_outreach,
        model_version: account.latest_score.model_version,
        timestamp: account.latest_score.timestamp,
        tokens_used: account.latest_score.tokens_used as any,
        latency_ms: account.latest_score.latency_ms,
        cost_usd: account.latest_score.cost_usd,
        version: account.latest_score.version,
      });
    } else {
      setScore(null);
    }

    const historyCacheKey = `${account.account_key}:${account.version || "v1"}`;
    const verCachedHistory = scoreHistoryCache.get(historyCacheKey);
    if (verCachedHistory && verCachedHistory.length > 0) {
      setScoreHistory(verCachedHistory);
      return;
    }

    // Load version-specific history from DB if not yet cached
    api.getScoreHistory(account.account_key, account.version)
      .then((res) => {
        if (res && res.history) {
          setScoreHistory(res.history);
          cacheScoreHistory(historyCacheKey, res.history);
          if (res.history.length > 0 && !account.latest_score) {
            const latest = res.history[0];
            setScore({
              account_key: account.account_key,
              account,
              score: latest.score,
              score_rationale: latest.score_rationale || undefined,
              priority_tier: latest.priority_tier,
              key_risks: latest.key_risks || [],
              suggested_outreach: latest.suggested_outreach,
              model_version: latest.model_version,
              timestamp: latest.timestamp,
              tokens_used: (latest.tokens_used as any) || { input: 0, output: 0 },
              latency_ms: latest.latency_ms || 0,
              cost_usd: latest.cost_usd || 0,
              version: latest.version,
            });
          }
        }
      })
      .catch((err) => {
        console.error("Failed to load score history:", err);
      });
  }, [account.account_key, account.version, cachedScore, cacheScoreHistory]);

  const handleScore = async () => {
    if (!currentUser) {
      openAuthModal("signin");
      return;
    }
    if (!currentUser.has_api_key) {
      openProfileModal();
      return;
    }

    setLoading(true);
    try {
      const result = await api.scoreAccount(account);
      setScore(result);
      addScore(result);
      const historyRes = await api.getScoreHistory(account.account_key);
      if (historyRes && historyRes.history) {
        setScoreHistory(historyRes.history);
        cacheScoreHistory(account.account_key, historyRes.history);
      }
    } catch (err: any) {
      console.error("Scoring failed:", err);
      const detail = err.response?.data?.detail || err.message || "Scoring failed";
      if (err.response?.status === 401) {
        openAuthModal("signin");
      } else if (err.response?.status === 400 && detail.includes("API key")) {
        openProfileModal();
      }
    } finally {
      setLoading(false);
    }
  };

  const copyText = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    setCopiedEntity(label);
    setTimeout(() => setCopiedEntity(null), 2000);
  };

  const copyOutreach = (outreachText?: string) => {
    const textToCopy = outreachText || score?.suggested_outreach;
    if (textToCopy) {
      copyText(textToCopy, "outreach");
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const getTierBadgeInfo = (tier?: string) => {
    switch (tier) {
      case "tier_1_critical":
        return { label: "Tier 1 · Critical", icon: "🚨", color: "#ef4444", bgClass: "badge-critical" };
      case "tier_2_high":
        return { label: "Tier 2 · High", icon: "🔥", color: "#f97316", bgClass: "badge-high" };
      case "tier_3_medium":
        return { label: "Tier 3 · Medium", icon: "⚡", color: "#eab308", bgClass: "badge-medium" };
      case "tier_4_low":
      default:
        return { label: "Tier 4 · Low", icon: "🛡️", color: "#22c55e", bgClass: "badge-low" };
    }
  };

  // Safe Array Wrappers
  const safeSignals = useMemo(() => account.signals || [], [account.signals]);
  const safeAssets = useMemo(() => account.assets || [], [account.assets]);
  const safeIps = useMemo(() => account.ips || [], [account.ips]);
  const safeHostnames = useMemo(() => account.hostnames || [], [account.hostnames]);
  const safeDomains = useMemo(() => account.domains || (account.domain ? [account.domain] : []), [account.domains, account.domain]);
  const safeProducts = useMemo(() => account.products || [], [account.products]);
  const safeCloudProviders = useMemo(() => account.cloud_providers || [], [account.cloud_providers]);

  const primaryDomain = account.domain || safeDomains[0] || account.account_key.replace("domain:", "");

  // 1. Smart Signal Rollup & Aggregation
  const { groupedSignals, severityCounts } = useMemo(() => {
    const map = new Map<string, {
      name: string;
      severity: "critical" | "high" | "medium" | "low";
      category: string;
      count: number;
      evidenceItems: string[];
    }>();

    const counts = { critical: 0, high: 0, medium: 0, low: 0, total: safeSignals.length };

    for (const s of safeSignals) {
      const sev = s.severity as "critical" | "high" | "medium" | "low";
      if (counts[sev] !== undefined) counts[sev]++;

      // Group by signal name to roll up duplicate individual CVE/finding lines
      const groupKey = s.name;
      const existing = map.get(groupKey);
      if (existing) {
        existing.count += 1;
        if (!existing.evidenceItems.includes(s.evidence)) {
          existing.evidenceItems.push(s.evidence);
        }
        // Upgrade severity if a higher severity instance exists
        const weight: Record<string, number> = { critical: 4, high: 3, medium: 2, low: 1 };
        if (weight[sev] > weight[existing.severity]) {
          existing.severity = sev;
        }
      } else {
        map.set(groupKey, {
          name: s.name,
          severity: sev,
          category: s.category || "vulnerability",
          count: 1,
          evidenceItems: [s.evidence],
        });
      }
    }

    const severityWeight: Record<string, number> = { critical: 4, high: 3, medium: 2, low: 1 };
    const rolledUpList = Array.from(map.values()).map((g) => {
      let consolidatedEvidence = "";
      const meta = SIGNAL_METADATA[g.name] || {
        label: g.name.replace(/_/g, " "),
        icon: "📌",
        description: "Security signal detected across perimeter scan data.",
      };

      if (g.name === "high_severity_vulnerability") {
        const scores = g.evidenceItems
          .map((e) => {
            const m = e.match(/score:\s*([\d.]+)/i);
            return m ? parseFloat(m[1]) : null;
          })
          .filter((v): v is number => v !== null);
        const maxCvss = scores.length > 0 ? Math.max(...scores).toFixed(1) : "10.0";
        consolidatedEvidence = `${g.count} critical/high vulnerabilities detected on perimeter (Max CVSS: ${maxCvss})`;
      } else if (g.name === "kev_vulnerability") {
        consolidatedEvidence = `${g.count} verified active in-the-wild exploited vulnerabilities (CISA KEV catalog)`;
      } else if (g.name === "ransomware_associated_vulnerability") {
        consolidatedEvidence = `${g.count} perimeter assets affected by documented ransomware campaign CVEs`;
      } else if (g.name === "eol_product") {
        const prods = g.evidenceItems.slice(0, 3).map((e) => e.replace(/End-of-life/i, "").trim()).filter(Boolean);
        consolidatedEvidence = `${g.count} End-of-Life unsupported software instances ${prods.length ? `(${prods.join(", ")})` : ""}`;
      } else if (g.name === "non_standard_exposed_port") {
        const portMatches = g.evidenceItems.map((e) => {
          const m = e.match(/\d+/);
          return m ? m[0] : null;
        }).filter(Boolean);
        const uniqueP = Array.from(new Set(portMatches)).slice(0, 5);
        consolidatedEvidence = `${g.count} services running on non-standard ports ${uniqueP.length ? `(${uniqueP.join(", ")})` : ""}`;
      } else if (g.name === "high_exploitation_probability") {
        consolidatedEvidence = `${g.count} vulnerabilities with elevated statistical EPSS weaponization probability`;
      } else if (g.name === "multiple_vulnerabilities") {
        consolidatedEvidence = `${g.count} perimeter hosts identified with dense multi-vulnerability clusters`;
      } else {
        consolidatedEvidence = g.evidenceItems.length === 1 ? g.evidenceItems[0] : `${g.count} telemetry findings recorded`;
      }

      return {
        ...g,
        label: meta.label,
        icon: meta.icon,
        description: meta.description,
        consolidatedEvidence,
      };
    }).sort((a, b) => {
      const diff = (severityWeight[b.severity] || 0) - (severityWeight[a.severity] || 0);
      if (diff !== 0) return diff;
      return b.count - a.count;
    });

    return { groupedSignals: rolledUpList, severityCounts: counts };
  }, [safeSignals]);

  const filteredGroupedSignals = useMemo(() => {
    return groupedSignals.filter((g) => {
      if (signalSeverityFilter !== "all" && g.severity !== signalSeverityFilter) return false;
      if (signalSearch.trim()) {
        const query = signalSearch.toLowerCase().trim();
        return (
          g.label.toLowerCase().includes(query) ||
          g.consolidatedEvidence.toLowerCase().includes(query) ||
          g.name.toLowerCase().includes(query) ||
          g.evidenceItems.some((e) => e.toLowerCase().includes(query))
        );
      }
      return true;
    });
  }, [groupedSignals, signalSeverityFilter, signalSearch]);

  const totalSignalPages = Math.max(1, Math.ceil(filteredGroupedSignals.length / signalPageSize));
  const paginatedSignals = useMemo(() => {
    const start = (signalPage - 1) * signalPageSize;
    return filteredGroupedSignals.slice(start, start + signalPageSize);
  }, [filteredGroupedSignals, signalPage]);

  // Port Classification Helper for Color-Coded Badges
  const getPortBadgeInfo = (port: number) => {
    if (HIGH_RISK_PORTS.has(port)) {
      return {
        cssClass: "port-critical",
        icon: "🚨",
        tierLabel: "High-Risk Management / Database",
      };
    }
    if ([8000, 8080, 8443, 8888, 9000, 9200, 8008, 3000, 5000].includes(port)) {
      return {
        cssClass: "port-warning",
        icon: "⚡",
        tierLabel: "Alt / Dev Service",
      };
    }
    if ([80, 443, 53].includes(port)) {
      return {
        cssClass: "port-standard",
        icon: "🌐",
        tierLabel: "Standard Web / DNS",
      };
    }
    return {
      cssClass: "port-info",
      icon: "🔌",
      tierLabel: "Custom Service",
    };
  };

  // Executive Brief Generator
  const handleCopyExecutiveBrief = () => {
    const critCount = severityCounts.critical;
    const highCount = severityCounts.high;
    const totalThreats = severityCounts.total;
    const scoreVal = score ? `${score.score}/100` : "Not Scored";
    const tierVal = currentTierBadge.label;

    const topRisks = score?.key_risks?.length
      ? score.key_risks.map((r) => `• ${r}`).join("\n")
      : "• Run Gemini AI evaluation to index key risk factors.";

    const pitch = score?.suggested_outreach
      ? score.suggested_outreach
      : "Run Gemini AI scoring to generate recommended outreach.";

    const topSignals = groupedSignals
      .slice(0, 6)
      .map((g) => `• [${g.severity.toUpperCase()}] ${g.label}: ${g.consolidatedEvidence}`)
      .join("\n");

    const brief = `🛡️ Security & Risk Executive Brief: ${primaryDomain}
=====================================================
• Priority Tier: ${tierVal}
• AI Risk Score: ${scoreVal}
• Threat Signals: ${totalThreats} total (${critCount} Critical, ${highCount} High)
• Attack Surface: ${perimeterEndpoints.length} endpoints · ${safeHostnames.length} subdomains · ${safeIps.length} IPs
• Cloud / Hosting: ${safeCloudProviders.join(", ") || "Self-Hosted / Datacenter"}

⚠️ Key Risk Factors:
${topRisks}

🚨 Consolidated Security Findings:
${topSignals || "• 0 active threat signals detected."}

🎯 Recommended Sales Outreach Angle:
"${pitch}"

=====================================================
Generated by Gemini Attack Surface Security Intelligence`;

    copyText(brief, "Executive Brief");
  };

  // 2. Unified Attack Surface & Perimeter Aggregation
  const perimeterEndpoints = useMemo<PerimeterEndpoint[]>(() => {
    const endpointMap = new Map<string, {
      hostname: string | null;
      ips: Set<string>;
      ports: Set<number>;
    }>();

    // Ingest all asset tuples
    for (const a of safeAssets) {
      const host = a.hostname?.trim() || null;
      const ip = a.ip?.trim() || null;
      const port = a.port;
      const key = host || ip || "unknown";

      if (!endpointMap.has(key)) {
        endpointMap.set(key, { hostname: host, ips: new Set(), ports: new Set() });
      }
      const entry = endpointMap.get(key)!;
      if (ip) entry.ips.add(ip);
      if (port !== null && port !== undefined) entry.ports.add(port);
    }

    // Include any hostnames not explicitly in assets
    for (const h of safeHostnames) {
      if (!endpointMap.has(h)) {
        endpointMap.set(h, { hostname: h, ips: new Set(), ports: new Set() });
      }
    }

    // Include any IPs not explicitly in assets
    for (const ip of safeIps) {
      if (!endpointMap.has(ip)) {
        endpointMap.set(ip, { hostname: null, ips: new Set([ip]), ports: new Set() });
      }
    }

    const domainRoot = primaryDomain.toLowerCase();

    return Array.from(endpointMap.entries()).map(([key, data]) => {
      const host = data.hostname;
      const isSubdomain = Boolean(host && (host.toLowerCase().endsWith("." + domainRoot) || host.toLowerCase() === domainRoot));
      const isSensitive = Boolean(host && SENSITIVE_SUBDOMAIN_PATTERNS.some((p) => host.toLowerCase().includes(p)));

      return {
        id: key,
        hostname: host,
        ip: Array.from(data.ips)[0] || (host ? null : key),
        ports: Array.from(data.ports).sort((a, b) => a - b),
        technologies: safeProducts,
        isSubdomain,
        isSensitive,
        cloudProvider: safeCloudProviders[0] || null,
      };
    }).sort((a, b) => {
      if (a.isSensitive !== b.isSensitive) return a.isSensitive ? -1 : 1;
      if (a.isSubdomain !== b.isSubdomain) return a.isSubdomain ? -1 : 1;
      return b.ports.length - a.ports.length;
    });
  }, [safeAssets, safeHostnames, safeIps, primaryDomain, safeProducts, safeCloudProviders]);

  const filteredPerimeter = useMemo(() => {
    const query = perimeterSearch.toLowerCase().trim();
    return perimeterEndpoints.filter((ep) => {
      if (perimeterFilter === "subdomains" && !ep.isSubdomain) return false;
      if (perimeterFilter === "sensitive" && !ep.isSensitive) return false;
      if (perimeterFilter === "risky_ports" && !ep.ports.some((p) => HIGH_RISK_PORTS.has(p))) return false;

      if (query) {
        const hostMatch = ep.hostname?.toLowerCase().includes(query) || false;
        const ipMatch = ep.ip?.toLowerCase().includes(query) || false;
        const portMatch = ep.ports.some((p) => p.toString().includes(query) || (COMMON_PORT_NAMES[p] && COMMON_PORT_NAMES[p].toLowerCase().includes(query)));
        const techMatch = ep.technologies.some((t) => t.toLowerCase().includes(query));
        return hostMatch || ipMatch || portMatch || techMatch;
      }
      return true;
    });
  }, [perimeterEndpoints, perimeterFilter, perimeterSearch]);

  const totalPerimeterPages = Math.max(1, Math.ceil(filteredPerimeter.length / perimeterPageSize));
  const paginatedPerimeter = useMemo(() => {
    const start = (perimeterPage - 1) * perimeterPageSize;
    return filteredPerimeter.slice(start, start + perimeterPageSize);
  }, [filteredPerimeter, perimeterPage]);

  const activeDisplayScore = inspectingHistoricalVersion || score;
  const currentTierBadge = getTierBadgeInfo(score?.priority_tier || account.priority_tier);
  const accountVersion: string = account.version || (account.account_key.includes(":v") ? account.account_key.split(":").pop() : "v1") || "v1";

  return (
    <div className="account-detail-container">
      {/* 1. Account Hero Card */}
      <div className="account-hero-card">
        <div className="hero-left-col">
          <div className="hero-title-row">
            <span className="hero-globe">🌐</span>
            <h1 className="hero-domain-title">{primaryDomain}</h1>
            <button
              className="hero-copy-btn"
              onClick={() => copyText(primaryDomain, "domain")}
              title="Copy primary domain"
            >
              📋
            </button>
            <span className={`hero-tier-pill ${currentTierBadge.bgClass}`}>
              {currentTierBadge.icon} {currentTierBadge.label}
            </span>
            {copiedEntity && <span className="hero-toast">✓ Copied {copiedEntity}!</span>}
          </div>

          <div className="hero-quick-stats">
            <button
              className={`hero-stat-chip ${activeTab === "signals" ? "active" : ""}`}
              onClick={() => handleTabChange("signals")}
            >
              🛡️ <strong>{severityCounts.total.toLocaleString()}</strong> Threat Signals
            </button>
            <button
              className={`hero-stat-chip ${activeTab === "perimeter" ? "active" : ""}`}
              onClick={() => handleTabChange("perimeter")}
            >
              🖥️ <strong>{(account.total_assets || perimeterEndpoints.length).toLocaleString()}</strong> Perimeter Endpoints
            </button>
            <button
              className={`hero-stat-chip ${activeTab === "perimeter" ? "active" : ""}`}
              onClick={() => {
                handleTabChange("perimeter");
                setPerimeterFilter("subdomains");
              }}
            >
              🏢 <strong>{(account.total_subdomains || safeHostnames.length).toLocaleString()}</strong> Subdomains
            </button>
            {safeCloudProviders.length > 0 && (
              <span className="hero-stat-chip cloud-chip">
                ☁️ {safeCloudProviders.join(", ")}
              </span>
            )}
          </div>
        </div>

        <div className="hero-right-col">
          {availableVersions && availableVersions.length > 1 ? (
            <div className="hero-snapshot-control">
              <span className="snapshot-control-label">📸 Snapshot:</span>
              <div className="snapshot-select-wrapper">
                <select
                  className="snapshot-select-input"
                  value={accountVersion.toLowerCase()}
                  onChange={(e) => {
                    setInspectingHistoricalVersion(null);
                    setExpandedSignalIdx(null);
                    onVersionChange?.(e.target.value);
                  }}
                  title="Switch attack surface snapshot version"
                >
                  {availableVersions.map((v) => {
                    const isActive = v.version.toLowerCase() === accountVersion.toLowerCase();
                    return (
                      <option key={v.version} value={v.version.toLowerCase()}>
                        {v.version.toUpperCase()} {isActive ? "(Current)" : ""} — {v.signals_count} Signals · {v.assets_count} Endpoints {v.ai_score ? `· Score ${v.ai_score}` : ""}
                      </option>
                    );
                  })}
                </select>
              </div>
            </div>
          ) : (
            <span className={`hero-version-pill ${accountVersion}`} title={`Scan Snapshot Version: ${accountVersion}`}>
              {accountVersion.toUpperCase()} (Latest)
            </span>
          )}

          <button
            className="hero-brief-btn"
            onClick={handleCopyExecutiveBrief}
            title="Copy structured Markdown summary of this account to clipboard"
          >
            📋 Copy Executive Brief
          </button>
          <button
            className={`hero-score-action-btn ${loading ? "loading" : ""} ${score ? "scored" : ""}`}
            onClick={handleScore}
            disabled={loading}
          >
            {loading ? (
              <>⏳ Analyzing with Gemini...</>
            ) : score ? (
              <>🔄 Re-Score Account</>
            ) : (
              <>⚡ Score Account with Gemini</>
            )}
          </button>
        </div>
      </div>

      {/* 2. Executive AI Intelligence Snapshot Banner (If Scored) */}
      {score && (
        <div className="executive-intel-banner">
          <div className="intel-score-gauge-box">
            <div className="intel-gauge-val" style={{ color: getTierBadgeInfo(score.priority_tier).color }}>
              {score.score}
              <span className="intel-gauge-max">/100</span>
            </div>
            <span className="intel-gauge-label">AI Risk Score</span>
          </div>

          <div className="intel-pitch-box">
            <div className="intel-box-title-row">
              <span className="intel-title-icon">🎯</span>
              <h4>Recommended Sales Outreach Angle</h4>
              <button className="intel-copy-btn" onClick={() => copyOutreach()}>
                {copied ? "✓ Copied!" : "📋 Copy Outreach"}
              </button>
            </div>
            <p className="intel-pitch-text">{score.suggested_outreach}</p>
          </div>

          <div className="intel-risks-box">
            <div className="intel-box-title-row">
              <span className="intel-title-icon">⚠️</span>
              <h4>Key Risk Highlights</h4>
            </div>
            <ul className="intel-risks-list">
              {score.key_risks.slice(0, 3).map((r, i) => (
                <li key={i}>{r}</li>
              ))}
            </ul>
          </div>
        </div>
      )}

      {/* 3. Master 3-Tab Navigation Bar */}
      <div className="detail-tab-nav-bar">
        <button
          className={`nav-tab-btn ${activeTab === "signals" ? "active" : ""}`}
          onClick={() => handleTabChange("signals")}
        >
          <span className="tab-icon">🛡️</span>
          <span className="tab-label">Security Signals &amp; Threats</span>
          <span className="tab-counter">{severityCounts.total}</span>
        </button>

        <button
          className={`nav-tab-btn ${activeTab === "perimeter" ? "active" : ""}`}
          onClick={() => handleTabChange("perimeter")}
        >
          <span className="tab-icon">🌐</span>
          <span className="tab-label">Attack Surface &amp; Perimeter</span>
          <span className="tab-counter">{perimeterEndpoints.length}</span>
        </button>

        <button
          className={`nav-tab-btn ${activeTab === "history" ? "active" : ""}`}
          onClick={() => handleTabChange("history")}
        >
          <span className="tab-icon">📜</span>
          <span className="tab-label">AI Intelligence &amp; Version History</span>
          {scoreHistory.length > 0 && <span className="tab-counter">v{scoreHistory[0]?.version || 1}</span>}
        </button>
      </div>

      {/* ========================================================================= */}
      {/* TAB 1: SECURITY SIGNALS & THREATS (Consolidated Rollup)                   */}
      {/* ========================================================================= */}
      {activeTab === "signals" && (
        <div className="tab-content-panel">
          <div className="panel-toolbar">
            <div className="severity-filter-chips">
              <button
                className={`filter-chip ${signalSeverityFilter === "all" ? "active" : ""}`}
                onClick={() => { setSignalSeverityFilter("all"); setSignalPage(1); }}
              >
                All ({severityCounts.total})
              </button>
              {severityCounts.critical > 0 && (
                <button
                  className={`filter-chip chip-critical ${signalSeverityFilter === "critical" ? "active" : ""}`}
                  onClick={() => { setSignalSeverityFilter("critical"); setSignalPage(1); }}
                >
                  🚨 Critical ({severityCounts.critical})
                </button>
              )}
              {severityCounts.high > 0 && (
                <button
                  className={`filter-chip chip-high ${signalSeverityFilter === "high" ? "active" : ""}`}
                  onClick={() => { setSignalSeverityFilter("high"); setSignalPage(1); }}
                >
                  🔥 High ({severityCounts.high})
                </button>
              )}
              {severityCounts.medium > 0 && (
                <button
                  className={`filter-chip chip-med ${signalSeverityFilter === "medium" ? "active" : ""}`}
                  onClick={() => { setSignalSeverityFilter("medium"); setSignalPage(1); }}
                >
                  ⚡ Medium ({severityCounts.medium})
                </button>
              )}
              {severityCounts.low > 0 && (
                <button
                  className={`filter-chip chip-low ${signalSeverityFilter === "low" ? "active" : ""}`}
                  onClick={() => { setSignalSeverityFilter("low"); setSignalPage(1); }}
                >
                  🛡️ Low ({severityCounts.low})
                </button>
              )}
            </div>

            <div className="toolbar-search-wrap">
              <input
                type="text"
                className="panel-search-input"
                placeholder="Search signals by CVE, port, category, keyword..."
                value={signalSearch}
                onChange={(e) => { setSignalSearch(e.target.value); setSignalPage(1); }}
              />
              {signalSearch && (
                <button className="search-clear-btn" onClick={() => setSignalSearch("")}>✕</button>
              )}
            </div>
          </div>

          {paginatedSignals.length === 0 ? (
            <div className="panel-empty-state">
              <span className="empty-icon">🛡️</span>
              <h4>No security signals match your filter criteria</h4>
              <p>Try switching the severity chip or clearing your search query.</p>
            </div>
          ) : (
            <div className="signals-table-container">
              <table className="clean-signals-table">
                <thead>
                  <tr>
                    <th style={{ width: "12%" }}>Severity</th>
                    <th style={{ width: "32%" }}>Signal Classification</th>
                    <th style={{ width: "14%" }}>Occurrences</th>
                    <th style={{ width: "42%" }}>Consolidated Telemetry &amp; Evidence</th>
                  </tr>
                </thead>
                <tbody>
                  {paginatedSignals.map((group, idx) => {
                    const isExpanded = expandedSignalIdx === idx;

                    return (
                      <tr key={idx} className={`signal-row row-${group.severity}`}>
                        <td>
                          <span className={`clean-severity-badge badge-${group.severity}`}>
                            {group.severity.toUpperCase()}
                          </span>
                        </td>
                        <td>
                          <div className="signal-name-cell">
                            <span className="signal-icon">{group.icon}</span>
                            <div>
                              <strong className="signal-primary-label">{group.label}</strong>
                              <span className="signal-subtext">{group.description}</span>
                            </div>
                          </div>
                        </td>
                        <td>
                          <span className="signal-occ-count">× {group.count.toLocaleString()}</span>
                        </td>
                        <td>
                          <div className="signal-evidence-wrap">
                            <span className="evidence-snippet">
                              {group.consolidatedEvidence}
                            </span>
                            {group.evidenceItems.length > 1 && (
                              <button
                                className="evidence-drawer-toggle-btn"
                                onClick={() => setExpandedSignalIdx(isExpanded ? null : idx)}
                              >
                                {isExpanded ? "Hide detailed items ▲" : `View ${group.evidenceItems.length} raw telemetry items ▼`}
                              </button>
                            )}
                            {isExpanded && (
                              <div className="raw-evidence-sublist">
                                {group.evidenceItems.map((item, i) => (
                                  <div key={i} className="raw-evidence-subitem">
                                    • {item}
                                  </div>
                                ))}
                              </div>
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

          {/* Pagination */}
          {totalSignalPages > 1 && (
            <div className="panel-pagination-footer">
              <span className="pag-info">
                Showing page <strong>{signalPage}</strong> of <strong>{totalSignalPages}</strong> ({filteredGroupedSignals.length} signals)
              </span>
              <div className="pag-actions">
                <button
                  className="pag-nav-btn"
                  disabled={signalPage === 1}
                  onClick={() => setSignalPage((p) => Math.max(1, p - 1))}
                >
                  ← Prev
                </button>
                <button
                  className="pag-nav-btn"
                  disabled={signalPage >= totalSignalPages}
                  onClick={() => setSignalPage((p) => p + 1)}
                >
                  Next →
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 2: ATTACK SURFACE & PERIMETER INVENTORY                               */}
      {/* ========================================================================= */}
      {activeTab === "perimeter" && (
        <div className="tab-content-panel">
          <div className="panel-toolbar">
            <div className="perimeter-filter-chips">
              <button
                className={`filter-chip ${perimeterFilter === "all" ? "active" : ""}`}
                onClick={() => { setPerimeterFilter("all"); setPerimeterPage(1); }}
              >
                All Endpoints ({perimeterEndpoints.length})
              </button>
              <button
                className={`filter-chip ${perimeterFilter === "subdomains" ? "active" : ""}`}
                onClick={() => { setPerimeterFilter("subdomains"); setPerimeterPage(1); }}
              >
                🏢 Subdomains Only ({perimeterEndpoints.filter((e) => e.isSubdomain).length})
              </button>
              <button
                className={`filter-chip ${perimeterFilter === "sensitive" ? "active" : ""}`}
                onClick={() => { setPerimeterFilter("sensitive"); setPerimeterPage(1); }}
              >
                ⚠️ Sensitive ({perimeterEndpoints.filter((e) => e.isSensitive).length})
              </button>
              <button
                className={`filter-chip ${perimeterFilter === "risky_ports" ? "active" : ""}`}
                onClick={() => { setPerimeterFilter("risky_ports"); setPerimeterPage(1); }}
              >
                🚨 Exposed Management Ports ({perimeterEndpoints.filter((e) => e.ports.some((p) => HIGH_RISK_PORTS.has(p))).length})
              </button>
            </div>

            <div className="toolbar-search-wrap">
              <input
                type="text"
                className="panel-search-input"
                placeholder="Search by subdomain, IP, port, software..."
                value={perimeterSearch}
                onChange={(e) => { setPerimeterSearch(e.target.value); setPerimeterPage(1); }}
              />
              {perimeterSearch && (
                <button className="search-clear-btn" onClick={() => setPerimeterSearch("")}>✕</button>
              )}
            </div>
          </div>

          {paginatedPerimeter.length === 0 ? (
            <div className="panel-empty-state">
              <span className="empty-icon">🌐</span>
              <h4>No perimeter assets match your filter criteria</h4>
              <p>Try switching filters or clearing your search term.</p>
            </div>
          ) : (
            <div className="perimeter-table-container">
              <table className="clean-perimeter-table">
                <thead>
                  <tr>
                    <th style={{ width: "32%" }}>Endpoint / Hostname</th>
                    <th style={{ width: "20%" }}>IP Address</th>
                    <th style={{ width: "28%" }}>Exposed Ports &amp; Services</th>
                    <th style={{ width: "20%" }}>Detected Technologies</th>
                  </tr>
                </thead>
                <tbody>
                  {paginatedPerimeter.map((ep) => (
                    <tr key={ep.id} className="perimeter-row">
                      {/* Hostname */}
                      <td>
                        <div className="endpoint-name-cell">
                          <span className="endpoint-icon">{ep.isSubdomain ? "🏢" : "🌐"}</span>
                          <span className="endpoint-name-text">
                            {ep.hostname || (ep.ip ? `Host (${ep.ip})` : "Direct IP Asset")}
                          </span>
                          {ep.isSensitive && (
                            <span className="sensitive-tag" title="Sensitive admin/portal/auth endpoint">
                              SENSITIVE
                            </span>
                          )}
                          {ep.hostname && (
                            <button
                              className="inline-copy-btn"
                              onClick={() => copyText(ep.hostname!, "hostname")}
                              title="Copy hostname"
                            >
                              📋
                            </button>
                          )}
                        </div>
                      </td>

                      {/* IP */}
                      <td>
                        {ep.ip ? (
                          <div className="ip-cell-wrap">
                            <span className="ip-mono">{ep.ip}</span>
                            <button
                              className="inline-copy-btn"
                              onClick={() => copyText(ep.ip!, "IP address")}
                              title="Copy IP"
                            >
                              📋
                            </button>
                          </div>
                        ) : (
                          <span className="text-muted">—</span>
                        )}
                      </td>

                      {/* Ports */}
                      <td>
                        {ep.ports.length === 0 ? (
                          <span className="text-muted">No open ports indexed</span>
                        ) : (
                          <div className="ports-pill-group">
                            {ep.ports.map((port) => {
                              const serviceName = COMMON_PORT_NAMES[port];
                              const badgeInfo = getPortBadgeInfo(port);
                              return (
                                <span
                                  key={port}
                                  className={`port-pill ${badgeInfo.cssClass}`}
                                  title={`${badgeInfo.tierLabel}: Port ${port}${serviceName ? ` (${serviceName})` : ""}`}
                                >
                                  <span className="port-tier-icon">{badgeInfo.icon}</span>
                                  <strong>{port}</strong>
                                  {serviceName && <span className="port-svc">{serviceName}</span>}
                                </span>
                              );
                            })}
                          </div>
                        )}
                      </td>

                      {/* Technologies */}
                      <td>
                        {ep.technologies.length === 0 ? (
                          <span className="text-muted">—</span>
                        ) : (
                          <div className="tech-pill-group">
                            {ep.technologies.slice(0, 4).map((tech, i) => (
                              <span key={i} className="tech-pill">
                                {tech}
                              </span>
                            ))}
                            {ep.technologies.length > 4 && (
                              <span className="tech-pill-more">+{ep.technologies.length - 4}</span>
                            )}
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* Pagination */}
          {totalPerimeterPages > 1 && (
            <div className="panel-pagination-footer">
              <span className="pag-info">
                Showing page <strong>{perimeterPage}</strong> of <strong>{totalPerimeterPages}</strong> ({filteredPerimeter.length} endpoints)
              </span>
              <div className="pag-actions">
                <button
                  className="pag-nav-btn"
                  disabled={perimeterPage === 1}
                  onClick={() => setPerimeterPage((p) => Math.max(1, p - 1))}
                >
                  ← Prev
                </button>
                <button
                  className="pag-nav-btn"
                  disabled={perimeterPage >= totalPerimeterPages}
                  onClick={() => setPerimeterPage((p) => p + 1)}
                >
                  Next →
                </button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 3: AI INTELLIGENCE & VERSION HISTORY                                  */}
      {/* ========================================================================= */}
      {activeTab === "history" && (
        <div className="tab-content-panel history-panel">
          {!score && scoreHistory.length === 0 ? (
            <div className="panel-empty-state">
              <span className="empty-icon">🤖</span>
              <h4>Account Has Not Been Scored Yet</h4>
              <p>Run Gemini AI evaluation to generate deep threat narratives, outreach angles, and security intelligence.</p>
              <button
                className="hero-score-action-btn"
                style={{ marginTop: "12px" }}
                onClick={handleScore}
                disabled={loading}
              >
                {loading ? "Analyzing..." : "⚡ Score Account Now"}
              </button>
            </div>
          ) : (
            <>
              {/* If inspecting a historical version, show the historical comparison snapshot card */}
              {inspectingHistoricalVersion ? (
                <div className="history-eval-card inspecting-historical">
                  <div className="eval-card-header">
                    <div className="eval-header-left">
                      <div className="eval-score-pill">
                        ⚡ {inspectingHistoricalVersion.score}/100
                      </div>
                      <div>
                        <h3 className="eval-card-title">
                          Historical Run Snapshot (v{inspectingHistoricalVersion.version})
                        </h3>
                        <span className="eval-meta-subtext">
                          Model: <code>{inspectingHistoricalVersion.model_version || "gemini-3.1-flash-lite"}</code> ·
                          Latency: <strong>{inspectingHistoricalVersion.latency_ms}ms</strong> ·
                          Cost: <strong>${(inspectingHistoricalVersion.cost_usd || 0).toFixed(5)}</strong>
                          {inspectingHistoricalVersion.timestamp && ` · ${new Date(inspectingHistoricalVersion.timestamp).toLocaleString()}`}
                        </span>
                      </div>
                    </div>
                    <button
                      className="eval-back-to-latest-btn"
                      onClick={() => setInspectingHistoricalVersion(null)}
                    >
                      ✕ Return to Latest (v{score?.version || scoreHistory[0]?.version || 1})
                    </button>
                  </div>

                  <div className="eval-card-body">
                    <div className="eval-section">
                      <h4>🎯 Historical Outreach Pitch (v{inspectingHistoricalVersion.version})</h4>
                      <div className="eval-box">
                        <p>{inspectingHistoricalVersion.suggested_outreach}</p>
                        <button
                          className="eval-copy-btn"
                          onClick={() => copyOutreach(inspectingHistoricalVersion.suggested_outreach)}
                        >
                          📋 Copy Pitch
                        </button>
                      </div>
                    </div>

                    <div className="eval-section">
                      <h4>⚠️ Historical Key Risks (v{inspectingHistoricalVersion.version})</h4>
                      <ul className="eval-risk-list">
                        {(inspectingHistoricalVersion.key_risks || []).map((r, i) => (
                          <li key={i}>{r}</li>
                        ))}
                      </ul>
                    </div>

                    {inspectingHistoricalVersion.score_rationale && inspectingHistoricalVersion.score_rationale !== inspectingHistoricalVersion.suggested_outreach && (
                      <div className="eval-section">
                        <h4>🧠 AI Analysis Rationale</h4>
                        <div className="eval-box rationale-text">
                          <p>{inspectingHistoricalVersion.score_rationale}</p>
                        </div>
                      </div>
                    )}
                  </div>
                </div>
              ) : (
                /* Default view: Show active model generation telemetry without duplicate pitch/risks */
                <div className="history-telemetry-card">
                  <div className="telemetry-grid">
                    <div className="telemetry-item">
                      <span className="telemetry-label">Active Model</span>
                      <strong className="telemetry-val">{score?.model_version || "gemini-3.1-flash-lite"}</strong>
                    </div>
                    <div className="telemetry-item">
                      <span className="telemetry-label">Inference Latency</span>
                      <strong className="telemetry-val">{score?.latency_ms || 0} ms</strong>
                    </div>
                    <div className="telemetry-item">
                      <span className="telemetry-label">Estimated Cost</span>
                      <strong className="telemetry-val">${(score?.cost_usd || 0).toFixed(5)}</strong>
                    </div>
                    <div className="telemetry-item">
                      <span className="telemetry-label">Token Consumption</span>
                      <strong className="telemetry-val">
                        {score?.tokens_used?.input || 0} in / {score?.tokens_used?.output || 0} out
                      </strong>
                    </div>
                    <div className="telemetry-item">
                      <span className="telemetry-label">Active Version</span>
                      <strong className="telemetry-val">v{score?.version || scoreHistory[0]?.version || 1}</strong>
                    </div>
                  </div>

                  {score?.score_rationale && score.score_rationale !== score.suggested_outreach && (
                    <div className="telemetry-rationale-box">
                      <h4>🧠 Deep AI Analysis &amp; Scoring Rationale</h4>
                      <p>{score.score_rationale}</p>
                    </div>
                  )}
                </div>
              )}

              {/* Version History Table */}
              <div className="version-history-section">
                <h3>📜 Version History ({scoreHistory.length} recorded {scoreHistory.length === 1 ? "run" : "runs"})</h3>
                {scoreHistory.length === 0 ? (
                  <p className="text-muted">Only the active score is recorded in session memory.</p>
                ) : (
                  <div className="history-table-wrap">
                    <table className="clean-history-table">
                      <thead>
                        <tr>
                          <th>Version</th>
                          <th>Score</th>
                          <th>Priority Tier</th>
                          <th>Model</th>
                          <th>Latency / Cost</th>
                          <th>Generated At</th>
                          <th>Action</th>
                        </tr>
                      </thead>
                      <tbody>
                        {scoreHistory.map((item) => {
                          const isCurrent = (activeDisplayScore?.version || scoreHistory[0]?.version) === item.version && !inspectingHistoricalVersion;
                          const isInspecting = inspectingHistoricalVersion?.version === item.version;

                          return (
                            <tr key={item.id || item.version} className={isCurrent ? "row-current" : ""}>
                              <td>
                                <strong className="ver-tag">v{item.version}</strong>
                                {item.version === scoreHistory[0]?.version && (
                                  <span className="latest-badge">LATEST</span>
                                )}
                              </td>
                              <td>
                                <strong className="ver-score">⚡ {item.score}/100</strong>
                              </td>
                              <td>
                                <span className={`clean-severity-badge ${getTierBadgeInfo(item.priority_tier).bgClass}`}>
                                  {getTierBadgeInfo(item.priority_tier).label}
                                </span>
                              </td>
                              <td>
                                <code className="model-code">{item.model_version || "gemini-3.1-flash-lite"}</code>
                              </td>
                              <td>
                                <span className="telemetry-text">
                                  {item.latency_ms}ms · ${item.cost_usd.toFixed(5)}
                                </span>
                              </td>
                              <td>
                                <span className="timestamp-text">
                                  {new Date(item.timestamp).toLocaleString()}
                                </span>
                              </td>
                              <td>
                                <button
                                  className="ver-inspect-btn"
                                  onClick={() => setInspectingHistoricalVersion(isInspecting ? null : item)}
                                >
                                  {isInspecting ? "Viewing" : "Inspect →"}
                                </button>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
};

export default AccountDetail;

import React, { useState, useEffect } from "react";
import { SummaryStats } from "../../types";
import { useAppStore } from "../../store";
import "./DashboardHeader.css";

export interface DashboardHeaderProps {
  summary: SummaryStats | null;
  activeTier?: string | null;
  onRefresh: () => void;
  onFilterChange?: (tier: string | null) => void;
  onOpenDeveloperSuite?: () => void;
  onOpenCrawlerApp?: () => void;
}

export const DashboardHeader: React.FC<DashboardHeaderProps> = ({
  summary,
  activeTier,
  onRefresh,
  onFilterChange,
  onOpenDeveloperSuite,
  onOpenCrawlerApp,
}) => {
  const [isDark, setIsDark] = useState(true);
  const [isRefreshing, setIsRefreshing] = useState(false);
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const { currentUser, openAuthModal, logout } = useAppStore();

  useEffect(() => {
    // Default to dark mode for enterprise security feel
    const savedTheme = localStorage.getItem("theme");
    if (savedTheme) {
      setIsDark(savedTheme === "dark");
      document.documentElement.setAttribute("data-theme", savedTheme);
    } else {
      setIsDark(true);
      document.documentElement.setAttribute("data-theme", "dark");
    }

    // Close dropdown on click outside
    const handleWindowClick = (e: MouseEvent) => {
      const target = e.target as HTMLElement;
      if (!target.closest(".user-profile-menu-container")) {
        setIsDropdownOpen(false);
      }
    };
    window.addEventListener("click", handleWindowClick);
    return () => window.removeEventListener("click", handleWindowClick);
  }, []);

  const toggleTheme = () => {
    const nextTheme = !isDark ? "dark" : "light";
    setIsDark(!isDark);
    localStorage.setItem("theme", nextTheme);
    document.documentElement.setAttribute("data-theme", nextTheme);
  };

  const handleRefreshClick = () => {
    setIsRefreshing(true);
    onRefresh();
    setTimeout(() => setIsRefreshing(false), 600);
  };

  const getPercent = (count?: number) => {
    if (!summary || !summary.total_accounts || !count) return "0%";
    return `${((count / summary.total_accounts) * 100).toFixed(1)}%`;
  };

  return (
    <header className="dashboard-header-container">
      {/* Top Sticky Navbar */}
      <div className="navbar-bar">
        <div className="navbar-left">
          <div className="brand-logo-wrap" onClick={() => onFilterChange?.(null)} style={{ cursor: "pointer" }}>
            <div className="brand-icon-shield">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                <path d="m9 12 2 2 4-4" />
              </svg>
            </div>
            <div>
              <div className="brand-title">
                Sales Intelligence <span className="brand-badge">PRO</span>
              </div>
              <div className="brand-subtitle">Automated Risk Scoring &amp; Outreach Engine</div>
            </div>
          </div>
        </div>

        <div className="navbar-right">
          <button
            className={`header-action-btn refresh-btn ${isRefreshing ? "spinning" : ""}`}
            onClick={handleRefreshClick}
            title="Refresh database records"
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
              <path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67" />
            </svg>
            <span>Refresh</span>
          </button>

          <button
            className="theme-switch-pill"
            onClick={toggleTheme}
            title={isDark ? "Switch to light mode" : "Switch to dark mode"}
            aria-label="Toggle color theme"
          >
            <span className={`theme-mode-icon ${!isDark ? "active-sun" : ""}`}>☀️</span>
            <span className={`theme-mode-icon ${isDark ? "active-moon" : ""}`}>🌙</span>
          </button>

          {/* User Profile Dropdown Menu */}
          {currentUser ? (
            <div className="user-profile-menu-container">
              <button
                type="button"
                className={`user-profile-nav-btn ${isDropdownOpen ? "active-open" : ""}`}
                onClick={(e) => {
                  e.stopPropagation();
                  setIsDropdownOpen(!isDropdownOpen);
                }}
                title="Account & Tools Menu"
                aria-expanded={isDropdownOpen}
              >
                <div className="nav-avatar">
                  {currentUser.email.charAt(0).toUpperCase()}
                </div>
                <span className="nav-user-email">
                  {currentUser.email.split("@")[0]}
                </span>
                <span className="dropdown-caret">▾</span>
              </button>

              {/* Interactive Profile Dropdown Menu */}
              {isDropdownOpen && (
                <div className="profile-dropdown-menu">
                  <div className="dropdown-user-header">
                    <div className="header-avatar-circle">
                      {currentUser.email.charAt(0).toUpperCase()}
                    </div>
                    <div className="header-user-text">
                      <span className="user-email-text">{currentUser.email}</span>
                      {currentUser.has_api_key ? (
                        <span className="user-key-badge-active">✓ Key Configured</span>
                      ) : (
                        <span className="user-key-badge-default">Using Server Quota</span>
                      )}
                    </div>
                  </div>

                  <div className="dropdown-menu-divider" />

                  <a
                    href="/documentation/index.html"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="dropdown-menu-item"
                    onClick={() => setIsDropdownOpen(false)}
                    style={{ textDecoration: "none", color: "inherit" }}
                  >
                    <span className="item-icon">📚</span>
                    <div className="item-text-group">
                      <span className="item-title">System Documentation</span>
                      <span className="item-desc">Architecture, user flows &amp; sequence diagrams</span>
                    </div>
                  </a>

                  <button
                    type="button"
                    className="dropdown-menu-item"
                    onClick={() => {
                      setIsDropdownOpen(false);
                      onOpenDeveloperSuite?.();
                    }}
                  >
                    <span className="item-icon">🧪</span>
                    <div className="item-text-group">
                      <span className="item-title">Developer Suite</span>
                      <span className="item-desc">API key management &amp; eval harness</span>
                    </div>
                  </button>

                  <button
                    type="button"
                    className="dropdown-menu-item"
                    onClick={() => {
                      setIsDropdownOpen(false);
                      onOpenCrawlerApp?.();
                    }}
                  >
                    <span className="item-icon">🌐</span>
                    <div className="item-text-group">
                      <span className="item-title">Web Crawler App</span>
                      <span className="item-desc">Perimeter scan &amp; domain discovery</span>
                    </div>
                  </button>

                  <div className="dropdown-menu-divider" />

                  <button
                    type="button"
                    className="dropdown-menu-item logout-item"
                    onClick={() => {
                      setIsDropdownOpen(false);
                      logout();
                    }}
                  >
                    <span className="item-icon">🚪</span>
                    <div className="item-text-group">
                      <span className="item-title">Sign Out</span>
                    </div>
                  </button>
                </div>
              )}
            </div>
          ) : (
            <button
              className="sign-in-nav-btn"
              onClick={() => openAuthModal("signin")}
              title="Sign In or Register"
            >
              <span>👤 Sign In</span>
            </button>
          )}
        </div>
      </div>

      {/* KPI Cards Hero Bar */}
      {summary && (
        <div className="kpi-banner">
          <button
            className={`kpi-card total-card ${!activeTier || activeTier === "all" ? "active-kpi" : ""}`}
            onClick={() => onFilterChange?.("all")}
          >
            <div className="kpi-top">
              <span className="kpi-label">Total Accounts</span>
              <span className="kpi-icon">🌐</span>
            </div>
            <div className="kpi-value">{summary.total_accounts.toLocaleString()}</div>
            <div className="kpi-subtext">All perimeter scans</div>
          </button>

          <button
            className={`kpi-card critical-card ${activeTier === "tier_1_critical" ? "active-kpi" : ""}`}
            onClick={() => onFilterChange?.("tier_1_critical")}
          >
            <div className="kpi-top">
              <span className="kpi-label">Tier 1 · Critical</span>
              <span className="kpi-icon">🚨</span>
            </div>
            <div className="kpi-value">{summary.critical_count.toLocaleString()}</div>
            <div className="kpi-subtext">
              <span className="kpi-pct">{getPercent(summary.critical_count)}</span> · Score 90–100
            </div>
          </button>

          <button
            className={`kpi-card high-card ${activeTier === "tier_2_high" ? "active-kpi" : ""}`}
            onClick={() => onFilterChange?.("tier_2_high")}
          >
            <div className="kpi-top">
              <span className="kpi-label">Tier 2 · High</span>
              <span className="kpi-icon">🔥</span>
            </div>
            <div className="kpi-value">{summary.high_count.toLocaleString()}</div>
            <div className="kpi-subtext">
              <span className="kpi-pct">{getPercent(summary.high_count)}</span> · Score 65–89
            </div>
          </button>

          <button
            className={`kpi-card medium-card ${activeTier === "tier_3_medium" ? "active-kpi" : ""}`}
            onClick={() => onFilterChange?.("tier_3_medium")}
          >
            <div className="kpi-top">
              <span className="kpi-label">Tier 3 · Medium</span>
              <span className="kpi-icon">⚡</span>
            </div>
            <div className="kpi-value">{summary.medium_count.toLocaleString()}</div>
            <div className="kpi-subtext">
              <span className="kpi-pct">{getPercent(summary.medium_count)}</span> · Score 40–64
            </div>
          </button>

          <button
            className={`kpi-card low-card ${activeTier === "tier_4_low" ? "active-kpi" : ""}`}
            onClick={() => onFilterChange?.("tier_4_low")}
          >
            <div className="kpi-top">
              <span className="kpi-label">Tier 4 · Low</span>
              <span className="kpi-icon">🛡️</span>
            </div>
            <div className="kpi-value">{summary.low_count.toLocaleString()}</div>
            <div className="kpi-subtext">
              <span className="kpi-pct">{getPercent(summary.low_count)}</span> · Score 1–39
            </div>
          </button>
        </div>
      )}
    </header>
  );
};

export default DashboardHeader;

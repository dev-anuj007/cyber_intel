import React, { useEffect, useState } from "react";
import { AccountDetail } from "../../components";
import { Account } from "../../types";
import { api } from "../../api";
import "./AccountDetailPage.css";

export interface AccountDetailPageProps {
  account?: Account | null;
  accountKey?: string;
  initialTab?: "signals" | "perimeter" | "history" | "assets" | "ips" | "domains" | "tech";
  onBack: () => void;
  onTabChange?: (tab: "signals" | "perimeter" | "history") => void;
}

export const AccountDetailPage: React.FC<AccountDetailPageProps> = ({
  account: initialAccount,
  accountKey: propAccountKey,
  initialTab,
  onBack,
  onTabChange,
}) => {
  const targetKey = initialAccount?.account_key || propAccountKey || "";
  const needsFullFetch = !initialAccount || !initialAccount.signals || initialAccount.signals.length === 0 || !initialAccount.assets || initialAccount.assets.length === 0;
  
  const [account, setAccount] = useState<Account | null>(initialAccount || null);
  const [loading, setLoading] = useState<boolean>(needsFullFetch);
  const [notFound, setNotFound] = useState<boolean>(false);

  useEffect(() => {
    if (!targetKey) {
      setNotFound(true);
      setLoading(false);
      return;
    }

    if (needsFullFetch || !initialAccount?.ports) {
      setLoading(true);
      setNotFound(false);
      api.getAccount(targetKey)
        .then((fullAccount) => {
          if (fullAccount) {
            setAccount(fullAccount);
          } else {
            setNotFound(true);
          }
        })
        .catch((err) => {
          console.error("Failed to load full account details:", err);
          setNotFound(true);
        })
        .finally(() => {
          setLoading(false);
        });
    } else {
      setAccount(initialAccount);
      setLoading(false);
    }
  }, [targetKey, needsFullFetch, initialAccount]);

  const primaryDomain = account?.domain || (account?.domains && account?.domains[0]) || targetKey.replace("domain:", "") || "Account Details";
  const extraDomainsCount = Math.max(0, (account?.domains?.length || 1) - 1);

  return (
    <div className="account-detail-page-container">
      {/* Breadcrumb Navigation Bar */}
      <div className="detail-breadcrumb-bar">
        <div className="breadcrumb-left-nav">
          <button type="button" className="breadcrumb-back-btn" onClick={onBack}>
            <span className="back-arrow">←</span>
            <span>Back to Accounts</span>
          </button>
          <span className="breadcrumb-slash">/</span>
          <span className="breadcrumb-target-name">{primaryDomain}</span>
        </div>

        {extraDomainsCount > 0 && (
          <span className="breadcrumb-extra-badge">
            +{extraDomainsCount} alias domains
          </span>
        )}
      </div>

      {/* Forensic Report Component */}
      <div className="detail-page-content-wrap">
        {loading ? (
          <div className="detail-loading-container">
            <div className="forensic-loader-card">
              <div className="forensic-spinner-wrapper">
                <div className="forensic-spinner-ring"></div>
                <div className="forensic-spinner-ring-inner"></div>
                <div className="forensic-spinner-core">🛡️</div>
              </div>
              <div className="forensic-loader-text-group">
                <h3 className="forensic-loader-title">Loading full forensic intelligence...</h3>
                <p className="forensic-loader-subtitle">
                  Retrieving complete attack surface inventory, exposed ports, software fingerprints, and threat signals for <code>{primaryDomain}</code>
                </p>
              </div>
              <div className="forensic-loader-progress-track">
                <div className="forensic-loader-progress-bar"></div>
              </div>
            </div>
          </div>
        ) : notFound || !account ? (
          <div className="detail-loading-container">
            <div className="forensic-loader-card">
              <div className="forensic-spinner-core" style={{ fontSize: "2rem", marginBottom: "8px" }}>⚠️</div>
              <div className="forensic-loader-text-group">
                <h3 className="forensic-loader-title">Account Not Found</h3>
                <p className="forensic-loader-subtitle">
                  Could not locate account record for <code>{targetKey}</code>.
                </p>
                <button
                  type="button"
                  className="breadcrumb-back-btn"
                  style={{ margin: "16px auto 0 auto", display: "inline-flex" }}
                  onClick={onBack}
                >
                  ← Return to Accounts List
                </button>
              </div>
            </div>
          </div>
        ) : (
          <AccountDetail account={account} initialTab={initialTab} onTabChange={onTabChange} />
        )}
      </div>
    </div>
  );
};

export default AccountDetailPage;

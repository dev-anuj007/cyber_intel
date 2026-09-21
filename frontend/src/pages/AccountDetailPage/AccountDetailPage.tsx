import React, { useEffect, useState, useRef } from "react";
import { AccountDetail } from "../../components";
import { Account } from "../../types";
import { api } from "../../api";
import { useAppStore } from "../../store";
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
  const { accountDetailsCache, cacheAccountDetail } = useAppStore();

  const cachedFullAccount = targetKey ? accountDetailsCache.get(targetKey) : null;
  const isFullAccount = (acc?: Account | null): boolean => {
    if (!acc) return false;
    return Boolean(
      acc.available_versions !== undefined &&
      ((acc.ports && acc.ports.length > 0) ||
        (acc.signals && acc.signals.length > 0) ||
        (acc.assets && acc.assets.length > 0) ||
        acc.total_signals_count !== undefined)
    );
  };

  const initialResolvedAccount: Account | null = cachedFullAccount || (isFullAccount(initialAccount) && initialAccount ? initialAccount : null);
  const [account, setAccount] = useState<Account | null>(initialResolvedAccount);
  const [loading, setLoading] = useState<boolean>(!initialResolvedAccount && Boolean(targetKey));
  const [notFound, setNotFound] = useState<boolean>(false);
  const lastFetchedKeyRef = useRef<string | null>(initialResolvedAccount ? targetKey : null);

  useEffect(() => {
    if (!targetKey) {
      setNotFound(true);
      setLoading(false);
      return;
    }

    const cached = useAppStore.getState().accountDetailsCache.get(targetKey);
    if (cached && isFullAccount(cached)) {
      setAccount(cached);
      setLoading(false);
      lastFetchedKeyRef.current = targetKey;
      return;
    }

    setLoading(true);
    setNotFound(false);
    lastFetchedKeyRef.current = targetKey;

    api.getAccount(targetKey)
      .then((fullAccount) => {
        if (fullAccount) {
          setAccount(fullAccount);
          cacheAccountDetail(fullAccount);
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
  }, [targetKey]);

  const handleVersionChange = async (version: string) => {
    const baseDom = account?.domain || targetKey.replace(/^domain:/, "").split(":")[0];
    const versionedKey = `domain:${baseDom}:${version}`;
    const cacheMap = useAppStore.getState().accountDetailsCache;
    const cached =
      cacheMap.get(versionedKey) ||
      cacheMap.get(`${targetKey}:${version}`) ||
      (account?.domain ? cacheMap.get(`domain:${account.domain}:${version}`) : null);

    if (cached && isFullAccount(cached)) {
      setAccount(cached);
      return;
    }

    setLoading(true);
    try {
      const fullAccount = await api.getAccount(targetKey, version);
      if (fullAccount) {
        setAccount(fullAccount);
        cacheAccountDetail(fullAccount);
      }
    } catch (err) {
      console.error("Failed to load versioned account details:", err);
    } finally {
      setLoading(false);
    }
  };

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
          <AccountDetail
            account={account}
            initialTab={initialTab}
            onTabChange={onTabChange}
            onVersionChange={handleVersionChange}
          />
        )}
      </div>
    </div>
  );
};

export default AccountDetailPage;

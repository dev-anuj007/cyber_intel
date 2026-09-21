import { useEffect, useState } from "react";
import { api } from "./api";
import { useAppStore } from "./store";
import { DashboardHeader, ProfileModal } from "./components";
import {
  AccountsPage,
  AccountDetailPage,
  DeveloperEvalPage,
  CrawlerAppPage,
  AuthPage,
} from "./pages";
import { parseCurrentRoute, navigateTo, ParsedRoute } from "./router";
import "./App.css";

function App() {
  const [route, setRoute] = useState<ParsedRoute>(() => parseCurrentRoute());

  const {
    summary,
    setLoading,
    setError,
    setSummary,
    selectAccount,
    selectedAccount,
    token,
    setToken,
    setCurrentUser,
  } = useAppStore();

  // Listen to browser navigation (Back, Forward, pushState, replaceState)
  useEffect(() => {
    const handlePopState = () => {
      setRoute(parseCurrentRoute());
    };

    window.addEventListener("popstate", handlePopState);
    return () => {
      window.removeEventListener("popstate", handlePopState);
    };
  }, []);

  useEffect(() => {
    if (token) {
      loadCurrentUser();
      loadDashboard();
    }
  }, [token]);

  const loadDashboard = async () => {
    setLoading(true);
    try {
      const data = await api.getSummary();
      setSummary(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load summary");
    } finally {
      setLoading(false);
    }
  };

  const loadCurrentUser = async () => {
    try {
      const user = await api.getCurrentUser();
      setCurrentUser(user);
    } catch (err) {
      console.warn("Session expired or invalid token:", err);
      setToken(null);
      setCurrentUser(null);
    }
  };

  // If user is not authenticated, land on Sign In / Sign Up full page
  if (!token) {
    return <AuthPage />;
  }

  return (
    <div className="app">
      <DashboardHeader
        summary={summary}
        activeTier={route.tier || null}
        onRefresh={loadDashboard}
        onFilterChange={(tier) => {
          navigateTo({ view: "list", tier: tier === "all" ? null : tier });
        }}
        onOpenDeveloperSuite={() => navigateTo({ view: "developer" })}
        onOpenCrawlerApp={() => navigateTo({ view: "crawler" })}
      />

      <main className="app-container">
        {route.view === "list" ? (
          <AccountsPage
            tierFilter={route.tier || null}
            onTierChange={(tier) => {
              navigateTo({ view: "list", tier: tier === "all" ? null : tier });
            }}
            onSelectAccount={(account, tab) => {
              selectAccount(account);
              navigateTo({
                view: "detail",
                accountKey: account.account_key,
                tab: tab || "signals",
                tier: route.tier,
              });
            }}
          />
        ) : route.view === "detail" && route.accountKey ? (
          <AccountDetailPage
            account={selectedAccount?.account_key === route.accountKey ? selectedAccount : null}
            accountKey={route.accountKey}
            initialTab={route.tab}
            onBack={() => {
              selectAccount(null);
              navigateTo({ view: "list", tier: route.tier });
            }}
            onTabChange={(newTab) => {
              navigateTo({
                view: "detail",
                accountKey: route.accountKey,
                tab: newTab,
                tier: route.tier,
                replace: true,
              });
            }}
          />
        ) : route.view === "developer" ? (
          <DeveloperEvalPage
            onBackToAccounts={() => navigateTo({ view: "list", tier: route.tier })}
          />
        ) : route.view === "crawler" ? (
          <CrawlerAppPage
            onBackToAccounts={() => {
              loadDashboard();
              navigateTo({ view: "list", tier: route.tier });
            }}
            onSelectAccount={(account) => {
              selectAccount(account);
              navigateTo({
                view: "detail",
                accountKey: account.account_key,
                tab: "signals",
              });
            }}
          />
        ) : (
          <AccountsPage
            tierFilter={route.tier || null}
            onTierChange={(tier) => {
              navigateTo({ view: "list", tier: tier === "all" ? null : tier });
            }}
            onSelectAccount={(account, tab) => {
              selectAccount(account);
              navigateTo({
                view: "detail",
                accountKey: account.account_key,
                tab: tab || "signals",
                tier: route.tier,
              });
            }}
          />
        )}
      </main>

      {/* Global Modals */}
      <ProfileModal onOpenDeveloperSuite={() => navigateTo({ view: "developer" })} />
    </div>
  );
}

export default App;

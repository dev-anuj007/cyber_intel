/**
 * Lightweight, robust URL routing & history management.
 * Persists page state, selected account, active tab, and filters on refresh.
 */

export type RouteView = "list" | "detail" | "developer" | "crawler";

export interface ParsedRoute {
  view: RouteView;
  accountKey?: string;
  tab?: "signals" | "perimeter" | "history";
  tier?: string | null;
}

export function parseCurrentRoute(): ParsedRoute {
  // Support standard pathname (e.g. /accounts/domain:abc) and hash fallback (e.g. #/accounts/domain:abc)
  let rawPath = window.location.pathname;
  let rawSearch = window.location.search;

  if (window.location.hash && window.location.hash.startsWith("#/")) {
    const hashPart = window.location.hash.slice(1);
    const [hPath, hQuery] = hashPart.split("?");
    rawPath = hPath;
    rawSearch = hQuery ? `?${hQuery}` : "";
  }

  const searchParams = new URLSearchParams(rawSearch);
  const tier = searchParams.get("tier");
  const tabParam = searchParams.get("tab") as any;
  const tab = ["signals", "perimeter", "history"].includes(tabParam) ? tabParam : undefined;

  const segments = rawPath.split("/").filter(Boolean);

  if (segments.length === 0) {
    return { view: "list", tier };
  }

  if (segments[0] === "accounts") {
    if (segments.length >= 2) {
      const accountKey = decodeURIComponent(segments.slice(1).join("/"));
      return {
        view: "detail",
        accountKey,
        tab,
        tier,
      };
    }
    return {
      view: "list",
      tier,
    };
  }

  if (segments[0] === "developer") {
    return { view: "developer" };
  }

  if (segments[0] === "crawler") {
    return { view: "crawler" };
  }

  if (segments[0] === "documentation") {
    if (!window.location.pathname.endsWith(".html")) {
      window.location.replace("/documentation/index.html");
    }
    return { view: "list", tier };
  }

  return { view: "list", tier };
}

export function navigateTo(route: {
  view: RouteView;
  accountKey?: string;
  tab?: string;
  tier?: string | null;
  replace?: boolean;
}) {
  let path = "/accounts";
  const params = new URLSearchParams();

  if (route.view === "list") {
    path = "/accounts";
    if (route.tier) params.set("tier", route.tier);
  } else if (route.view === "detail" && route.accountKey) {
    path = `/accounts/${encodeURIComponent(route.accountKey)}`;
    if (route.tab) params.set("tab", route.tab);
  } else if (route.view === "developer") {
    path = "/developer";
  } else if (route.view === "crawler") {
    path = "/crawler";
  }

  const queryString = params.toString() ? `?${params.toString()}` : "";
  const fullUrl = `${path}${queryString}`;

  if (route.replace) {
    window.history.replaceState({ ...route }, "", fullUrl);
  } else {
    window.history.pushState({ ...route }, "", fullUrl);
  }

  window.dispatchEvent(new Event("popstate"));
}

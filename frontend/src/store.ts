import { create } from "zustand";
import { Account, AccountScore, SummaryStats, UserProfile, AuthModalMode } from "./types";

interface AppStore {
  accounts: Account[];
  scores: Map<string, AccountScore>;
  summary: SummaryStats | null;
  loading: boolean;
  error: string | null;
  selectedAccount: Account | null;
  selectedScore: AccountScore | null;

  // Auth & Profile State
  currentUser: UserProfile | null;
  token: string | null;
  isAuthModalOpen: boolean;
  isProfileModalOpen: boolean;
  authModalMode: AuthModalMode;

  setAccounts: (accounts: Account[]) => void;
  addScore: (score: AccountScore) => void;
  setSummary: (summary: SummaryStats) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
  selectAccount: (account: Account | null) => void;
  selectScore: (score: AccountScore | null) => void;

  // Auth & Profile Actions
  setCurrentUser: (user: UserProfile | null) => void;
  setToken: (token: string | null) => void;
  openAuthModal: (mode?: AuthModalMode) => void;
  closeAuthModal: () => void;
  openProfileModal: () => void;
  closeProfileModal: () => void;
  logout: () => void;
}

export const useAppStore = create<AppStore>((set) => ({
  accounts: [],
  scores: new Map(),
  summary: null,
  loading: false,
  error: null,
  selectedAccount: null,
  selectedScore: null,

  currentUser: null,
  token: localStorage.getItem("token"),
  isAuthModalOpen: false,
  isProfileModalOpen: false,
  authModalMode: "signin",

  setAccounts: (accounts) => set({ accounts }),
  addScore: (score) =>
    set((state) => {
      const newScores = new Map(state.scores);
      newScores.set(score.account_key, score);
      return { scores: newScores };
    }),
  setSummary: (summary) => set({ summary }),
  setLoading: (loading) => set({ loading }),
  setError: (error) => set({ error }),
  selectAccount: (account) => set({ selectedAccount: account }),
  selectScore: (score) => set({ selectedScore: score }),

  setCurrentUser: (user) => set({ currentUser: user }),
  setToken: (token) => {
    if (token) {
      localStorage.setItem("token", token);
    } else {
      localStorage.removeItem("token");
    }
    set({ token });
  },
  openAuthModal: (mode = "signin") =>
    set({ isAuthModalOpen: true, authModalMode: mode, isProfileModalOpen: false }),
  closeAuthModal: () => set({ isAuthModalOpen: false }),
  openProfileModal: () =>
    set({ isProfileModalOpen: true, isAuthModalOpen: false }),
  closeProfileModal: () => set({ isProfileModalOpen: false }),
  logout: () => {
    localStorage.removeItem("token");
    set({
      token: null,
      currentUser: null,
      isProfileModalOpen: false,
    });
  },
}));

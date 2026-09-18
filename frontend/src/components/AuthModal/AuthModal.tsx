import React, { useState } from "react";
import { api } from "../../api";
import { useAppStore } from "../../store";
import "./AuthModal.css";

export const AuthModal: React.FC = () => {
  const {
    isAuthModalOpen,
    closeAuthModal,
    authModalMode,
    openAuthModal,
    setCurrentUser,
    setToken,
  } = useAppStore();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  if (!isAuthModalOpen) return null;

  const isSignIn = authModalMode === "signin";

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMsg(null);

    const cleanEmail = email.trim();
    if (!cleanEmail) {
      setErrorMsg("Please enter your email address.");
      return;
    }
    if (!password) {
      setErrorMsg("Please enter your password.");
      return;
    }
    if (!isSignIn && password.length < 6) {
      setErrorMsg("Password must be at least 6 characters long.");
      return;
    }

    setLoading(true);
    try {
      const res = isSignIn
        ? await api.signin(cleanEmail, password)
        : await api.signup(cleanEmail, password);

      setToken(res.token);
      setCurrentUser(res.user);
      closeAuthModal();
      setEmail("");
      setPassword("");
    } catch (err: any) {
      const detail =
        err.response?.data?.detail || err.message || "Authentication failed";
      setErrorMsg(detail);
    } finally {
      setLoading(false);
    }
  };

  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      closeAuthModal();
    }
  };

  return (
    <div className="auth-modal-overlay" onClick={handleBackdropClick}>
      <div className="auth-modal-card">
        {/* Modal Header */}
        <div className="auth-modal-header">
          <div className="auth-brand-area">
            <div className="auth-shield-icon">
              <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                <path d="m9 12 2 2 4-4" />
              </svg>
            </div>
            <div>
              <h3 className="auth-title">
                {isSignIn ? "Sign In to Platform" : "Create Enterprise Account"}
              </h3>
              <p className="auth-subtitle">
                {isSignIn
                  ? "Access your personalized scoring workspace & API keys"
                  : "Start scoring accounts with custom Gemini API keys"}
              </p>
            </div>
          </div>
          <button
            className="auth-close-btn"
            onClick={closeAuthModal}
            title="Close (Esc)"
          >
            ✕
          </button>
        </div>

        {/* Tab Switch */}
        <div className="auth-tab-switch">
          <button
            className={`auth-tab-btn ${isSignIn ? "active" : ""}`}
            onClick={() => {
              setErrorMsg(null);
              openAuthModal("signin");
            }}
          >
            Sign In
          </button>
          <button
            className={`auth-tab-btn ${!isSignIn ? "active" : ""}`}
            onClick={() => {
              setErrorMsg(null);
              openAuthModal("signup");
            }}
          >
            Sign Up
          </button>
        </div>

        {/* Form Body */}
        <form className="auth-form" onSubmit={handleSubmit}>
          {errorMsg && (
            <div className="auth-error-alert">
              <span className="error-icon">⚠️</span>
              <span>{errorMsg}</span>
            </div>
          )}

          <div className="auth-field-group">
            <label className="auth-label">Email Address</label>
            <div className="auth-input-wrap">
              <span className="input-adornment-icon">✉️</span>
              <input
                type="email"
                className="auth-input"
                placeholder="sdr@enterprise.com"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                autoFocus
                required
              />
            </div>
          </div>

          <div className="auth-field-group">
            <label className="auth-label">Password</label>
            <div className="auth-input-wrap">
              <span className="input-adornment-icon">🔒</span>
              <input
                type={showPassword ? "text" : "password"}
                className="auth-input"
                placeholder={isSignIn ? "••••••••" : "At least 6 characters"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
              />
              <button
                type="button"
                className="pwd-toggle-btn"
                onClick={() => setShowPassword(!showPassword)}
                title={showPassword ? "Hide password" : "Show password"}
              >
                {showPassword ? "👁️" : "👁️‍🗨️"}
              </button>
            </div>
          </div>

          <button
            type="submit"
            className="auth-submit-btn"
            disabled={loading}
          >
            {loading ? (
              <span className="auth-btn-loading">
                <span className="auth-spinner"></span>
                <span>{isSignIn ? "Signing In..." : "Creating Account..."}</span>
              </span>
            ) : (
              <span>{isSignIn ? "Sign In →" : "Sign Up & Get Started →"}</span>
            )}
          </button>
        </form>

        {/* Footer switch prompt */}
        <div className="auth-modal-footer">
          {isSignIn ? (
            <p>
              Don't have an account?{" "}
              <button
                type="button"
                className="switch-link-btn"
                onClick={() => {
                  setErrorMsg(null);
                  openAuthModal("signup");
                }}
              >
                Sign Up
              </button>
            </p>
          ) : (
            <p>
              Already have an account?{" "}
              <button
                type="button"
                className="switch-link-btn"
                onClick={() => {
                  setErrorMsg(null);
                  openAuthModal("signin");
                }}
              >
                Sign In
              </button>
            </p>
          )}
        </div>
      </div>
    </div>
  );
};

export default AuthModal;

import React, { useState } from "react";
import { api } from "../../api";
import { useAppStore } from "../../store";
import "./AuthPage.css";

export const AuthPage: React.FC = () => {
  const { setToken, setCurrentUser } = useAppStore();
  const [mode, setMode] = useState<"signin" | "signup">("signin");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const isSignIn = mode === "signin";

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
    } catch (err: any) {
      const detail =
        err.response?.data?.detail || err.message || "Authentication failed";
      setErrorMsg(detail);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-page-container">
      {/* Background glowing gradients */}
      <div className="auth-bg-blob auth-bg-blob-1"></div>
      <div className="auth-bg-blob auth-bg-blob-2"></div>

      <div className="auth-page-card-layout">
        {/* Left Side: Product Showcase & Brand Values */}
        <div className="auth-showcase-panel">
          <div className="showcase-brand-header">
            <div className="showcase-brand-logo">
              <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                <path d="m9 12 2 2 4-4" />
              </svg>
            </div>
            <div>
              <h1 className="showcase-brand-title">
                Sales Intelligence <span className="pro-badge">PRO</span>
              </h1>
              <p className="showcase-brand-tagline">
                Automated Risk Scoring &amp; Outreach Engine
              </p>
            </div>
          </div>

          <div className="showcase-features-list">
            <div className="showcase-feature-item">
              <div className="feature-icon-box">🛡️</div>
              <div className="feature-text-content">
                <div className="feature-title">Perimeter Attack Surface Intelligence</div>
                <div className="feature-desc">
                  Explore 50,000+ accounts indexed with live open ports, technologies, and vulnerabilities.
                </div>
              </div>
            </div>

            <div className="showcase-feature-item">
              <div className="feature-icon-box">⚡</div>
              <div className="feature-text-content">
                <div className="feature-title">AI Prospecting &amp; Scoring Engine</div>
                <div className="feature-desc">
                  Bring your personal Gemini API key for custom LLM scoring, threat rationales, and tailored pitch synthesis.
                </div>
              </div>
            </div>

            <div className="showcase-feature-item">
              <div className="feature-icon-box">🚨</div>
              <div className="feature-text-content">
                <div className="feature-title">CISA KEV &amp; Ransomware Prioritization</div>
                <div className="feature-desc">
                  Instant 4-tier calibration separating low-risk accounts from urgent exploitation threats.
                </div>
              </div>
            </div>
          </div>

          <div className="showcase-security-footer">
            <span className="security-lock-icon">🔒</span>
            <span>Enterprise-Grade Session Security &amp; Encrypted Key Vault</span>
          </div>
        </div>

        {/* Right Side: Authentication Form */}
        <div className="auth-form-panel">
          <div className="auth-form-header">
            <h2 className="auth-form-title">
              {isSignIn ? "Welcome Back" : "Create Your Account"}
            </h2>
            <p className="auth-form-subtitle">
              {isSignIn
                ? "Sign in to access your sales intelligence workspace"
                : "Sign up to start prospecting with AI threat scoring"}
            </p>
          </div>

          {/* Mode Tabs */}
          <div className="auth-mode-tabs">
            <button
              type="button"
              className={`mode-tab-btn ${isSignIn ? "active" : ""}`}
              onClick={() => {
                setErrorMsg(null);
                setMode("signin");
              }}
            >
              Sign In
            </button>
            <button
              type="button"
              className={`mode-tab-btn ${!isSignIn ? "active" : ""}`}
              onClick={() => {
                setErrorMsg(null);
                setMode("signup");
              }}
            >
              Sign Up
            </button>
          </div>

          {/* Form */}
          <form className="auth-page-form" onSubmit={handleSubmit}>
            {errorMsg && (
              <div className="auth-page-error-banner">
                <span className="error-icon">⚠️</span>
                <span>{errorMsg}</span>
              </div>
            )}

            <div className="auth-input-group">
              <label className="input-label">Work Email</label>
              <div className="input-field-wrapper">
                <span className="field-icon">✉️</span>
                <input
                  type="email"
                  className="page-auth-input"
                  placeholder="name@company.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  autoFocus
                  required
                />
              </div>
            </div>

            <div className="auth-input-group">
              <label className="input-label">Password</label>
              <div className="input-field-wrapper">
                <span className="field-icon">🔒</span>
                <input
                  type={showPassword ? "text" : "password"}
                  className="page-auth-input"
                  placeholder={isSignIn ? "••••••••" : "Minimum 6 characters"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
                <button
                  type="button"
                  className="page-pwd-toggle"
                  onClick={() => setShowPassword(!showPassword)}
                  title={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? "👁️" : "👁️‍🗨️"}
                </button>
              </div>
            </div>

            <button
              type="submit"
              className="page-auth-submit-btn"
              disabled={loading}
            >
              {loading ? (
                <span className="submit-spinner-wrap">
                  <span className="page-spinner"></span>
                  <span>{isSignIn ? "Authenticating..." : "Creating Account..."}</span>
                </span>
              ) : (
                <span>{isSignIn ? "Sign In to Workspace →" : "Create Account & Get Started →"}</span>
              )}
            </button>
          </form>

          {/* Footer toggle */}
          <div className="auth-page-footer">
            {isSignIn ? (
              <p>
                Don't have an account yet?{" "}
                <button
                  type="button"
                  className="inline-mode-toggle-btn"
                  onClick={() => {
                    setErrorMsg(null);
                    setMode("signup");
                  }}
                >
                  Sign Up Free
                </button>
              </p>
            ) : (
              <p>
                Already have an account?{" "}
                <button
                  type="button"
                  className="inline-mode-toggle-btn"
                  onClick={() => {
                    setErrorMsg(null);
                    setMode("signin");
                  }}
                >
                  Sign In
                </button>
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default AuthPage;

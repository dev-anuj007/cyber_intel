import React, { useState } from "react";
import { api } from "../../api";
import { useAppStore } from "../../store";
import "./ProfileModal.css";


interface ProfileModalProps {
  onOpenDeveloperSuite?: () => void;
}

export const ProfileModal: React.FC<ProfileModalProps> = ({ onOpenDeveloperSuite }) => {
  const {
    isProfileModalOpen,
    closeProfileModal,
    currentUser,
    setCurrentUser,
    logout,
  } = useAppStore();

  const [apiKeyInput, setApiKeyInput] = useState("");
  const [showKey, setShowKey] = useState(false);
  const [loading, setLoading] = useState(false);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  if (!isProfileModalOpen || !currentUser) return null;

  const handleLaunchDevSuite = () => {
    closeProfileModal();
    if (onOpenDeveloperSuite) {
      onOpenDeveloperSuite();
    }
  };

  const handleSaveApiKey = async (e: React.FormEvent) => {
    e.preventDefault();
    setSuccessMsg(null);
    setErrorMsg(null);

    const cleanKey = apiKeyInput.trim();
    if (!cleanKey) {
      setErrorMsg("Please enter a valid Google Gemini API key.");
      return;
    }

    setLoading(true);
    try {
      const updatedUser = await api.updateApiKey(cleanKey);
      setCurrentUser(updatedUser);
      setApiKeyInput("");
      setSuccessMsg("Your Gemini API key has been saved and is now active for all LLM calls!");
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch (err: any) {
      const detail =
        err.response?.data?.detail || err.message || "Failed to update API key";
      setErrorMsg(detail);
    } finally {
      setLoading(false);
    }
  };

  const handleRemoveApiKey = async () => {
    setSuccessMsg(null);
    setErrorMsg(null);
    setLoading(true);
    try {
      const updatedUser = await api.deleteApiKey();
      setCurrentUser(updatedUser);
      setSuccessMsg("API key removed. The platform will now use the system default key.");
      setTimeout(() => setSuccessMsg(null), 3000);
    } catch (err: any) {
      const detail =
        err.response?.data?.detail || err.message || "Failed to remove API key";
      setErrorMsg(detail);
    } finally {
      setLoading(false);
    }
  };

  const handleBackdropClick = (e: React.MouseEvent) => {
    if (e.target === e.currentTarget) {
      closeProfileModal();
    }
  };

  return (
    <div className="profile-modal-overlay" onClick={handleBackdropClick}>
      <div className="profile-modal-card">
        {/* Modal Header */}
        <div className="profile-modal-header">
          <div className="profile-user-info">
            <div className="profile-avatar-circle">
              {currentUser.email.charAt(0).toUpperCase()}
            </div>
            <div>
              <h3 className="profile-email">{currentUser.email}</h3>
              <span className="profile-role-badge">Enterprise Sales Account</span>
            </div>
          </div>
          <button
            className="profile-close-btn"
            onClick={closeProfileModal}
            title="Close (Esc)"
          >
            ✕
          </button>
        </div>

        {/* Modal Body */}
        <div className="profile-modal-body">
          {/* Notifications */}
          {successMsg && (
            <div className="profile-success-alert">
              <span>✓</span>
              <span>{successMsg}</span>
            </div>
          )}

          {errorMsg && (
            <div className="profile-error-alert">
              <span>⚠️</span>
              <span>{errorMsg}</span>
            </div>
          )}

          {/* Active Key Status Card */}
          <div className="api-key-status-card">
            <div className="status-top-row">
              <span className="status-title">🔑 Gemini API Key Status</span>
              {currentUser.has_api_key ? (
                <span className="key-active-badge">
                  ✓ Custom Key Active
                </span>
              ) : (
                <span className="key-default-badge">
                  Using System Default
                </span>
              )}
            </div>

            <div className="status-details">
              {currentUser.has_api_key ? (
                <div className="key-preview-wrap">
                  <span className="key-preview-text">
                    Active Key: <code>{currentUser.api_key_preview || "Configured"}</code>
                  </span>
                  <button
                    type="button"
                    className="key-delete-btn"
                    onClick={handleRemoveApiKey}
                    disabled={loading}
                    title="Remove custom key and revert to system default"
                  >
                    Remove Key
                  </button>
                </div>
              ) : (
                <p className="status-desc">
                  No personal API key configured. Account scoring and outreach generation will use the server's shared Gemini API quota.
                </p>
              )}
            </div>
          </div>

          {/* Add / Update Key Form */}
          <form className="api-key-form" onSubmit={handleSaveApiKey}>
            <div className="form-heading-group">
              <label className="key-input-label">
                {currentUser.has_api_key ? "Update Gemini API Key" : "Add Personal Gemini API Key"}
              </label>
              <span className="key-helper-link">
                <a
                  href="https://aistudio.google.com/app/apikey"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Get API Key ↗
                </a>
              </span>
            </div>

            <div className="key-input-wrapper">
              <input
                type={showKey ? "text" : "password"}
                className="api-key-input"
                placeholder="AIzaSy..."
                value={apiKeyInput}
                onChange={(e) => setApiKeyInput(e.target.value)}
                required
              />
              <button
                type="button"
                className="key-mask-toggle-btn"
                onClick={() => setShowKey(!showKey)}
                title={showKey ? "Hide key" : "Show key"}
              >
                {showKey ? "👁️" : "👁️‍🗨️"}
              </button>
            </div>

            <div className="api-key-guidance">
              <span className="guidance-icon">ℹ️</span>
              <p>
                Your API key is securely encrypted and used exclusively for your account scoring, outreach drafting, and batch intelligence workflows.
              </p>
            </div>

            <button
              type="submit"
              className="save-key-btn"
              disabled={loading || !apiKeyInput.trim()}
            >
              {loading ? "Saving Key..." : currentUser.has_api_key ? "Update API Key" : "Save & Activate API Key"}
            </button>
          </form>

          {/* Developer Suite Launch Card */}
          <div className="dev-options-callout-card">
            <div className="dev-callout-left">
              <div className="dev-callout-title">
                <span>🧪 Developer Suite &amp; Eval Harness</span>
                <span className="dev-callout-tag">Prompt Engineering</span>
              </div>
              <p className="dev-callout-desc">
                Evaluate scoring accuracy against 25 labeled test cases, edit prompt templates, and run side-by-side benchmark comparisons.
              </p>
            </div>
            <button
              type="button"
              className="dev-launch-btn"
              onClick={handleLaunchDevSuite}
            >
              <span>Open Developer Suite</span>
              <span>↗</span>
            </button>
          </div>
        </div>

        {/* Modal Footer */}
        <div className="profile-modal-footer">
          <button
            type="button"
            className="sign-out-btn"
            onClick={logout}
          >
            <span>🚪</span>
            <span>Sign Out</span>
          </button>
        </div>
      </div>
    </div>
  );
};

export default ProfileModal;



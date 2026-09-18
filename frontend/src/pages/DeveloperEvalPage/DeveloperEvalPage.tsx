import React, { useState, useEffect } from "react";
import { api } from "../../api";
import { useAppStore } from "../../store";
import {
  PromptTemplateInfo,
  EvalResultData,
  EvalComparisonData,
  EvalHistoryItem,
} from "../../types";
import "./DeveloperEvalPage.css";

interface Props {
  onBackToAccounts: () => void;
}

type DevPageTab = "single-run" | "benchmark-compare" | "history-logs";

export const DeveloperEvalPage: React.FC<Props> = ({ onBackToAccounts }) => {
  const { currentUser, openProfileModal, openAuthModal } = useAppStore();
  const [activeTab, setActiveTab] = useState<DevPageTab>("single-run");

  // Prompts
  const [prompts, setPrompts] = useState<PromptTemplateInfo[]>([]);

  // Single Eval Run State
  const [selectedPrompt, setSelectedPrompt] = useState<string>("v2.0");
  const [customPrompt, setCustomPrompt] = useState<string>("");
  const [isCustomPrompt, setIsCustomPrompt] = useState<boolean>(false);
  const [dryRun, setDryRun] = useState<boolean>(true);
  const [evalLoading, setEvalLoading] = useState<boolean>(false);
  const [evalResult, setEvalResult] = useState<EvalResultData | null>(null);
  const [evalError, setEvalError] = useState<string | null>(null);
  const [searchFilter, setSearchFilter] = useState<string>("");

  // Compare State
  const [comparePromptA, setComparePromptA] = useState<string>("v1.0");
  const [comparePromptB, setComparePromptB] = useState<string>("v2.0");
  const [compareDryRun, setCompareDryRun] = useState<boolean>(true);
  const [compareLoading, setCompareLoading] = useState<boolean>(false);
  const [comparisonData, setComparisonData] = useState<EvalComparisonData | null>(null);
  const [compareError, setCompareError] = useState<string | null>(null);

  // Dataset Configuration State
  const [datasetMode, setDatasetMode] = useState<"standard" | "subset" | "custom">("standard");
  const [defaultDataset, setDefaultDataset] = useState<any[]>([]);
  const [customDatasetJson, setCustomDatasetJson] = useState<string>("");
  const [sampleLimit, setSampleLimit] = useState<number>(5);
  const [datasetValidationMsg, setDatasetValidationMsg] = useState<{ type: "success" | "error" | "info"; text: string } | null>(null);

  // History State
  const [historyItems, setHistoryItems] = useState<EvalHistoryItem[]>([]);
  const [historyLoading, setHistoryLoading] = useState<boolean>(false);
  const [historyPage, setHistoryPage] = useState<number>(1);
  const HISTORY_PAGE_SIZE = 10;

  useEffect(() => {
    loadPrompts();
    loadDataset();
    loadHistory();
  }, []);

  const loadDataset = async () => {
    try {
      const data = await api.getEvalDataset();
      if (data && data.dataset) {
        setDefaultDataset(data.dataset);
        setCustomDatasetJson(JSON.stringify(data.dataset, null, 2));
      }
    } catch (err) {
      console.warn("Failed to load eval dataset from backend:", err);
    }
  };

  const loadPrompts = async () => {
    try {
      const data = await api.getEvalPrompts();
      if (data && data.prompts) {
        setPrompts(data.prompts);
        const scoringV2 = data.prompts.find((p: any) => p.version === "v2.0" || p.name.includes("v2.0"));
        if (scoringV2) {
          setCustomPrompt(scoringV2.template);
        } else if (data.prompts.length > 0) {
          setCustomPrompt(data.prompts[0].template);
        }
      }
    } catch (err) {
      console.warn("Failed to load prompts:", err);
    }
  };

  const loadHistory = async () => {
    setHistoryLoading(true);
    try {
      const data = await api.getEvalHistory();
      if (data && data.history) {
        setHistoryItems(data.history);
      }
    } catch (err) {
      console.warn("Failed to load history:", err);
    } finally {
      setHistoryLoading(false);
    }
  };

  const handlePromptSelectChange = (ver: string) => {
    if (ver === "custom") {
      setIsCustomPrompt(true);
    } else {
      setIsCustomPrompt(false);
      setSelectedPrompt(ver);
      const matched = prompts.find((p) => p.version === ver);
      if (matched) {
        setCustomPrompt(matched.template);
      }
    }
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = (event) => {
      try {
        const content = event.target?.result as string;
        const parsed = JSON.parse(content);
        if (!Array.isArray(parsed)) {
          setDatasetValidationMsg({ type: "error", text: "Uploaded JSON must be an array of benchmark accounts." });
          return;
        }
        setCustomDatasetJson(JSON.stringify(parsed, null, 2));
        setDatasetValidationMsg({ type: "success", text: `Loaded ${parsed.length} accounts from file: ${file.name}` });
      } catch (err: any) {
        setDatasetValidationMsg({ type: "error", text: `Invalid JSON file: ${err.message}` });
      }
    };
    reader.readAsText(file);
  };

  const validateCustomDataset = (): any[] => {
    try {
      const parsed = JSON.parse(customDatasetJson);
      if (!Array.isArray(parsed)) {
        throw new Error("Dataset must be a JSON array of benchmark test cases.");
      }
      if (parsed.length === 0) {
        throw new Error("Dataset array cannot be empty.");
      }
      for (let i = 0; i < parsed.length; i++) {
        const item = parsed[i];
        if (!item.account_key) {
          throw new Error(`Sample #${i + 1} missing required 'account_key' property.`);
        }
        if (!item.expected_tier) {
          throw new Error(`Sample #${i + 1} (${item.account_key}) missing required 'expected_tier'.`);
        }
        if (typeof item.expected_score !== "number") {
          throw new Error(`Sample #${i + 1} (${item.account_key}) missing numeric 'expected_score'.`);
        }
      }
      setDatasetValidationMsg({ type: "success", text: `✓ Valid dataset with ${parsed.length} benchmark accounts.` });
      return parsed;
    } catch (err: any) {
      setDatasetValidationMsg({ type: "error", text: err.message });
      throw err;
    }
  };

  const getActiveDatasetParams = () => {
    if (datasetMode === "custom") {
      const parsed = validateCustomDataset();
      return { eval_set: parsed, sample_limit: undefined };
    }
    if (datasetMode === "subset") {
      return { eval_set: undefined, sample_limit: sampleLimit };
    }
    return { eval_set: undefined, sample_limit: undefined };
  };

  const handleExecuteEval = async () => {
    if (!dryRun) {
      if (!currentUser) {
        openAuthModal("signin");
        setEvalError("Please sign in to execute live AI evaluations.");
        return;
      }
      if (!currentUser.has_api_key) {
        openProfileModal();
        setEvalError("Please configure your Gemini API key in Profile settings to run live scoring.");
        return;
      }
    }

    let datasetParams: { eval_set?: any[]; sample_limit?: number };
    try {
      datasetParams = getActiveDatasetParams();
    } catch (err: any) {
      setEvalError(err.message);
      return;
    }

    setEvalLoading(true);
    setEvalError(null);
    try {
      const resp = await api.runEval({
        prompt_version: isCustomPrompt ? "custom" : selectedPrompt,
        custom_prompt_template: isCustomPrompt ? customPrompt : undefined,
        dry_run: dryRun,
        eval_set: datasetParams.eval_set,
        sample_limit: datasetParams.sample_limit,
      });

      if (resp && resp.results) {
        setEvalResult(resp.results);
        loadHistory();
      } else {
        throw new Error("Invalid response format from eval runner");
      }
    } catch (err: any) {
      const detail = err.response?.data?.detail || err.message || "Evaluation execution failed";
      setEvalError(detail);
      if (err.response?.status === 401) {
        openAuthModal("signin");
      } else if (err.response?.status === 400 && detail.includes("API key")) {
        openProfileModal();
      }
    } finally {
      setEvalLoading(false);
    }
  };

  const handleExecuteCompare = async () => {
    if (!compareDryRun) {
      if (!currentUser) {
        openAuthModal("signin");
        setCompareError("Please sign in to execute live prompt comparisons.");
        return;
      }
      if (!currentUser.has_api_key) {
        openProfileModal();
        setCompareError("Please configure your Gemini API key in Profile settings to run live comparisons.");
        return;
      }
    }

    let datasetParams: { eval_set?: any[]; sample_limit?: number };
    try {
      datasetParams = getActiveDatasetParams();
    } catch (err: any) {
      setCompareError(err.message);
      return;
    }

    setCompareLoading(true);
    setCompareError(null);
    try {
      const resp = await api.compareEval({
        prompt_a: comparePromptA,
        prompt_b: comparePromptB,
        dry_run: compareDryRun,
        eval_set: datasetParams.eval_set,
        sample_limit: datasetParams.sample_limit,
      });
      if (resp && resp.comparison) {
        setComparisonData(resp.comparison);
      } else {
        throw new Error("Invalid response from comparison runner");
      }
    } catch (err: any) {
      const detail = err.response?.data?.detail || err.message || "Benchmark comparison failed";
      setCompareError(detail);
      if (err.response?.status === 401) {
        openAuthModal("signin");
      } else if (err.response?.status === 400 && detail.includes("API key")) {
        openProfileModal();
      }
    } finally {
      setCompareLoading(false);
    }
  };

  const handleViewHistoricalResult = async (filename: string) => {
    setEvalLoading(true);
    setEvalError(null);
    try {
      const data = await api.getEvalResultFile(filename);
      if (data && data.results) {
        setEvalResult(data.results);
        setActiveTab("single-run");
        window.scrollTo({ top: 300, behavior: "smooth" });
      }
    } catch (err) {
      setEvalError("Failed to load historical result file");
    } finally {
      setEvalLoading(false);
    }
  };

  const formatPct = (val?: number | null) =>
    typeof val === "number" && !isNaN(val) ? `${(val * 100).toFixed(1)}%` : "—";

  const filteredPredictions = evalResult?.predictions.filter((p) => {
    if (!searchFilter) return true;
    const q = searchFilter.toLowerCase();
    return (
      p.expected_tier.toLowerCase().includes(q) ||
      p.predicted_tier.toLowerCase().includes(q) ||
      p.suggested_outreach.toLowerCase().includes(q) ||
      p.key_risks.some((r) => r.toLowerCase().includes(q))
    );
  }) || [];

  return (
    <div className="dev-page-wrapper">
      {/* Top Breadcrumb Header Bar */}
      <div className="dev-breadcrumb-bar">
        <div className="dev-breadcrumb-left">
          <button className="dev-back-btn" onClick={onBackToAccounts}>
            <span>←</span>
            <span>Back to Accounts</span>
          </button>
          <span className="dev-breadcrumb-sep">/</span>
          <span className="dev-breadcrumb-title">Developer &amp; Eval Suite</span>
        </div>

        <div className="dev-breadcrumb-right">
          {currentUser?.has_api_key ? (
            <span className="dev-key-status-chip active" onClick={openProfileModal}>
              ✓ Custom Key Active ({currentUser.api_key_preview || "Configured"})
            </span>
          ) : (
            <span className="dev-key-status-chip" onClick={openProfileModal}>
              Using Server Shared Key · Click to configure personal API key ↗
            </span>
          )}
        </div>
      </div>

      {/* Hero Welcome Banner */}
      <div className="dev-hero-card">
        <div className="dev-hero-info">
          <div className="dev-hero-badge">🧪 LLM Eval Harness &amp; Benchmark Studio</div>
          <h2 className="dev-hero-title">Account Scoring Prompt Engineering &amp; Evaluation</h2>
          <p className="dev-hero-desc">
            Test prompt revisions against hand-labeled cybersecurity ground truth data (<code>eval_v1.json</code>), verify zero missed critical threats, and generate rigorous side-by-side performance benchmarks.
          </p>
        </div>

        <div className="dev-hero-stats">
          <div className="hero-stat-box">
            <span className="hero-stat-label">Ground Truth Set</span>
            <span className="hero-stat-val">25 Accounts</span>
          </div>
          <div className="hero-stat-box">
            <span className="hero-stat-label">Target Tier Recall</span>
            <span className="hero-stat-val">100.0%</span>
          </div>
          <div className="hero-stat-box">
            <span className="hero-stat-label">Production Prompt</span>
            <span className="hero-stat-val">v2.0 Calibrated</span>
          </div>
        </div>
      </div>

      {/* Master Mode Switcher Tabs */}
      <div className="dev-page-tabs">
        <button
          type="button"
          className={`dev-page-tab-btn ${activeTab === "single-run" ? "active" : ""}`}
          onClick={() => setActiveTab("single-run")}
        >
          <span>🚀</span>
          <span>Single Prompt Evaluation</span>
        </button>

        <button
          type="button"
          className={`dev-page-tab-btn ${activeTab === "benchmark-compare" ? "active" : ""}`}
          onClick={() => setActiveTab("benchmark-compare")}
        >
          <span>⚖️</span>
          <span>Prompt Benchmark Comparison</span>
        </button>

        <button
          type="button"
          className={`dev-page-tab-btn ${activeTab === "history-logs" ? "active" : ""}`}
          onClick={() => setActiveTab("history-logs")}
        >
          <span>📜</span>
          <span>Historical Run Logs ({historyItems.length})</span>
        </button>
      </div>

      {/* =================================================================== */}
      {/* VIEW 1: SINGLE EVALUATION RUN                                      */}
      {/* =================================================================== */}
      {activeTab === "single-run" && (
        <div className="dev-page-section">
          <div className="dev-card config-panel">
            <div className="dev-card-header">
              <h3 className="section-title">1. Configure Evaluation Parameters</h3>
              <span className="dataset-indicator">
                {datasetMode === "custom"
                  ? "🛠️ Custom Frontend Dataset"
                  : datasetMode === "subset"
                  ? `⚡ Fast Subset (${sampleLimit} Samples)`
                  : `📦 Standard Dataset (${defaultDataset.length || 25} Accounts)`}
              </span>
            </div>

            <div className="config-row-grid">
              <div className="config-field">
                <label className="field-label">Target Prompt Version</label>
                <select
                  className="field-select"
                  value={isCustomPrompt ? "custom" : selectedPrompt}
                  onChange={(e) => handlePromptSelectChange(e.target.value)}
                  disabled={evalLoading}
                >
                  <option value="v2.0">v2.0 (Calibrated - Production)</option>
                  <option value="v1.0">v1.0 (Baseline Initial)</option>
                  <option value="custom">✏️ Custom Prompt Template (Interactive Editor)...</option>
                </select>
              </div>

              <div className="config-field">
                <label className="field-label">Execution Strategy</label>
                <div className="mode-toggle-group">
                  <button
                    type="button"
                    className={`toggle-btn ${dryRun ? "active" : ""}`}
                    onClick={() => setDryRun(true)}
                  >
                    ⚡ Fast Dry-Run (Heuristic · 0 Quota)
                  </button>
                  <button
                    type="button"
                    className={`toggle-btn ${!dryRun ? "active" : ""}`}
                    onClick={() => setDryRun(false)}
                  >
                    ✨ Live Gemini API ({currentUser?.has_api_key ? "Personal Key" : "System Quota"})
                  </button>
                </div>
              </div>
            </div>

            {/* Custom Prompt Interactive Editor */}
            {isCustomPrompt && (
              <div className="prompt-editor-container">
                <div className="prompt-editor-top">
                  <span className="editor-label">Custom Prompt Template</span>
                  <span className="editor-hint">
                    Required placeholder: <code>{`{account_context}`}</code>
                  </span>
                </div>
                <textarea
                  className="prompt-code-editor"
                  rows={10}
                  value={customPrompt}
                  onChange={(e) => setCustomPrompt(e.target.value)}
                  placeholder="Enter your system prompt instructions..."
                  disabled={evalLoading}
                />
              </div>
            )}

            {/* Evaluation Dataset Configuration Card */}
            <div className="dataset-config-box">
              <div className="dataset-config-header">
                <div className="dataset-header-title">
                  <span className="dataset-icon">📊</span>
                  <div>
                    <div className="dataset-title-text">Evaluation Benchmark Dataset</div>
                    <div className="dataset-subtitle-text">
                      Choose standard ground truth, select a quick sample size, or provide custom JSON test cases.
                    </div>
                  </div>
                </div>

                <div className="dataset-mode-pills">
                  <button
                    type="button"
                    className={`dataset-pill-btn ${datasetMode === "standard" ? "active" : ""}`}
                    onClick={() => {
                      setDatasetMode("standard");
                      setDatasetValidationMsg(null);
                    }}
                  >
                    📦 Standard ({defaultDataset.length || 25})
                  </button>
                  <button
                    type="button"
                    className={`dataset-pill-btn ${datasetMode === "subset" ? "active" : ""}`}
                    onClick={() => {
                      setDatasetMode("subset");
                      setDatasetValidationMsg(null);
                    }}
                  >
                    ⚡ Fast Subset ({sampleLimit})
                  </button>
                  <button
                    type="button"
                    className={`dataset-pill-btn ${datasetMode === "custom" ? "active" : ""}`}
                    onClick={() => {
                      setDatasetMode("custom");
                    }}
                  >
                    🛠️ Custom JSON
                  </button>
                </div>
              </div>

              {/* Subset Quick Sizer */}
              {datasetMode === "subset" && (
                <div className="dataset-subset-controls">
                  <span className="subset-label">Select Sample Size:</span>
                  {[3, 5, 10, 15, 25].map((size) => (
                    <button
                      key={size}
                      type="button"
                      className={`subset-size-btn ${sampleLimit === size ? "active" : ""}`}
                      onClick={() => setSampleLimit(size)}
                    >
                      {size} Samples
                    </button>
                  ))}
                  <span className="subset-hint">⚡ Evaluated in ~{Math.max(1, Math.round(sampleLimit * 0.6))}s with parallel workers</span>
                </div>
              )}

              {/* Custom JSON Dataset Editor */}
              {datasetMode === "custom" && (
                <div className="custom-dataset-editor-wrap">
                  <div className="dataset-editor-toolbar">
                    <div className="editor-tools-left">
                      <span className="editor-toolbar-title">Benchmark JSON Array</span>
                      <button
                        type="button"
                        className="btn-toolbar-action"
                        onClick={() => {
                          setCustomDatasetJson(JSON.stringify(defaultDataset, null, 2));
                          setDatasetValidationMsg({ type: "info", text: "Loaded default template into editor" });
                        }}
                      >
                        Reset Template
                      </button>
                      <button
                        type="button"
                        className="btn-toolbar-action"
                        onClick={() => {
                          try {
                            const p = JSON.parse(customDatasetJson);
                            setCustomDatasetJson(JSON.stringify(p, null, 2));
                            setDatasetValidationMsg({ type: "success", text: `Valid JSON with ${p.length} items.` });
                          } catch (err: any) {
                            setDatasetValidationMsg({ type: "error", text: `Syntax error: ${err.message}` });
                          }
                        }}
                      >
                        Format JSON
                      </button>
                    </div>

                    <div className="editor-tools-right">
                      <label className="btn-upload-label">
                        📁 Upload JSON
                        <input
                          type="file"
                          accept=".json,application/json"
                          style={{ display: "none" }}
                          onChange={handleFileUpload}
                        />
                      </label>
                    </div>
                  </div>

                  <textarea
                    className="dataset-json-textarea"
                    rows={8}
                    value={customDatasetJson}
                    onChange={(e) => {
                      setCustomDatasetJson(e.target.value);
                      setDatasetValidationMsg(null);
                    }}
                    placeholder='[\n  {\n    "account_key": "domain:test.com",\n    "expected_tier": "tier_1_critical",\n    "expected_score": 95,\n    "critical_signals": ["ransomware_associated_vulnerability"]\n  }\n]'
                  />

                  {datasetValidationMsg && (
                    <div className={`dataset-msg-banner msg-${datasetValidationMsg.type}`}>
                      <span>{datasetValidationMsg.type === "error" ? "❌" : "✓"}</span>
                      <span>{datasetValidationMsg.text}</span>
                    </div>
                  )}
                </div>
              )}
            </div>

            <div className="dev-action-bar">
              <button
                type="button"
                className="btn-primary-run"
                onClick={handleExecuteEval}
                disabled={evalLoading}
              >
                {evalLoading ? (
                  <>
                    <span className="page-spinner" />
                    <span>Evaluating {datasetMode === "subset" ? `${sampleLimit} Subset` : datasetMode === "custom" ? "Custom" : "25"} Benchmark Cases...</span>
                  </>
                ) : (
                  <>
                    <span>🚀</span>
                    <span>Run Evaluation ({datasetMode === "subset" ? `${sampleLimit} Samples` : datasetMode === "custom" ? "Custom Set" : `${defaultDataset.length || 25} Ground Truth`})</span>
                  </>
                )}
              </button>
            </div>
          </div>

          {evalError && (
            <div className="dev-alert-danger">
              <span>⚠️</span>
              <span>{evalError}</span>
            </div>
          )}

          {/* Results Visualizer */}
          {evalResult && (
            <div className="results-visualizer">
              <div className="results-top-banner">
                <div className="results-title-group">
                  <span className="results-badge">Evaluation Complete</span>
                  <h4 className="results-heading">
                    Score &amp; Signal Quality Report · <code>{evalResult.prompt_version}</code>
                  </h4>
                </div>
                <span className="total-badge">{evalResult.total} Test Cases</span>
              </div>

              {/* KPI Score Cards */}
              <div className="metrics-kpi-row">
                <div className="kpi-box highlight-blue">
                  <span className="kpi-heading">Tier Accuracy</span>
                  <span className="kpi-number">{formatPct(evalResult.tier_accuracy)}</span>
                  <span className="kpi-annotation">Industry Target &gt; 90%</span>
                </div>

                <div className="kpi-box">
                  <span className="kpi-heading">Macro F1-Score</span>
                  <span className="kpi-number">{evalResult.macro_f1.toFixed(3)}</span>
                  <span className="kpi-annotation">Balanced multi-class</span>
                </div>

                <div className="kpi-box highlight-green">
                  <span className="kpi-heading">Critical Threat Recall</span>
                  <span className="kpi-number">{formatPct(evalResult.critical_threat_recall)}</span>
                  <span className="kpi-annotation">Zero Missed Threats</span>
                </div>

                <div className="kpi-box">
                  <span className="kpi-heading">Score MAE</span>
                  <span className="kpi-number">{evalResult.score_mae.toFixed(2)} pts</span>
                  <span className="kpi-annotation">Mean Absolute Error</span>
                </div>

                <div className="kpi-box">
                  <span className="kpi-heading">Accuracy within ±5 Pts</span>
                  <span className="kpi-number">{evalResult.within_5_points_pct.toFixed(1)}%</span>
                  <span className="kpi-annotation">{evalResult.within_5_points} of {evalResult.total} examples</span>
                </div>
              </div>

              {/* Per-Tier Breakdown Table */}
              <div className="dev-card">
                <h4 className="card-heading">Per-Tier Precision, Recall &amp; F1 Matrix</h4>
                <div className="dev-table-container">
                  <table className="dev-table">
                    <thead>
                      <tr>
                        <th>Priority Tier</th>
                        <th>Precision</th>
                        <th>Recall</th>
                        <th>F1-Score</th>
                        <th>Support (Ground Truth)</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(evalResult.tier_metrics || {}).map(([tierKey, m]) => (
                        <tr key={tierKey}>
                          <td>
                            <span className={`tier-badge-pill ${tierKey}`}>
                              {tierKey.replace("tier_", "").replace("_", " ").toUpperCase()}
                            </span>
                          </td>
                          <td>{(m.precision * 100).toFixed(1)}%</td>
                          <td>{(m.recall * 100).toFixed(1)}%</td>
                          <td><strong>{m.f1_score.toFixed(3)}</strong></td>
                          <td>{m.support} accounts</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Predictions Table with Search */}
              <div className="dev-card">
                <div className="card-header-with-search">
                  <h4 className="card-heading">Test Case Predictions ({evalResult.predictions.length})</h4>
                  <input
                    type="text"
                    className="prediction-search-input"
                    placeholder="Filter test cases..."
                    value={searchFilter}
                    onChange={(e) => setSearchFilter(e.target.value)}
                  />
                </div>

                <div className="predictions-list">
                  {filteredPredictions.map((p, i) => (
                    <div key={i} className={`prediction-card ${p.tier_match ? "success" : "mismatch"}`}>
                      <div className="pred-header">
                        <span className="pred-index">Case #{i + 1}</span>
                        <div className="pred-comparison">
                          <span>Expected: <strong>{p.expected_tier.replace("tier_", "")}</strong> ({p.expected_score} pts)</span>
                          <span>➜</span>
                          <span>Predicted: <strong className={p.tier_match ? "text-green" : "text-red"}>{p.predicted_tier.replace("tier_", "")}</strong> ({p.predicted_score} pts)</span>
                        </div>
                        <span className={`pred-badge ${p.tier_match ? "badge-pass" : "badge-fail"}`}>
                          {p.tier_match ? "✓ Match" : `Error: Δ ${p.score_error} pts`}
                        </span>
                      </div>

                      {p.suggested_outreach && (
                        <div className="pred-evidence">
                          <strong>Outreach Pitch:</strong> <em>"{p.suggested_outreach}"</em>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* =================================================================== */}
      {/* VIEW 2: PROMPT BENCHMARK COMPARISON                                */}
      {/* =================================================================== */}
      {activeTab === "benchmark-compare" && (
        <div className="dev-page-section">
          <div className="dev-card config-panel">
            <div className="dev-card-header">
              <h3 className="section-title">1. Select Prompt Versions to Compare</h3>
              <span className="dataset-indicator">Direct Side-by-Side Delta Analysis</span>
            </div>

            <div className="compare-grid">
              <div className="config-field">
                <label className="field-label">Baseline (Prompt A)</label>
                <select
                  className="field-select"
                  value={comparePromptA}
                  onChange={(e) => setComparePromptA(e.target.value)}
                  disabled={compareLoading}
                >
                  <option value="v1.0">v1.0 (Baseline Initial)</option>
                  <option value="v2.0">v2.0 (Calibrated)</option>
                </select>
              </div>

              <div className="vs-divider">
                <span>VS</span>
              </div>

              <div className="config-field">
                <label className="field-label">Candidate (Prompt B)</label>
                <select
                  className="field-select"
                  value={comparePromptB}
                  onChange={(e) => setComparePromptB(e.target.value)}
                  disabled={compareLoading}
                >
                  <option value="v2.0">v2.0 (Calibrated - Production)</option>
                  <option value="v1.0">v1.0 (Baseline)</option>
                </select>
              </div>
            </div>

            <div className="dev-action-bar">
              <button
                type="button"
                className="btn-primary-run"
                onClick={handleExecuteCompare}
                disabled={compareLoading}
              >
                {compareLoading ? (
                  <>
                    <span className="page-spinner" />
                    <span>Executing Benchmark Comparison...</span>
                  </>
                ) : (
                  <>
                    <span>⚖️</span>
                    <span>Run Side-by-Side Comparison</span>
                  </>
                )}
              </button>

              <div className="mode-toggle-group">
                <button
                  type="button"
                  className={`toggle-btn ${compareDryRun ? "active" : ""}`}
                  onClick={() => setCompareDryRun(true)}
                >
                  ⚡ Fast Dry-Run
                </button>
                <button
                  type="button"
                  className={`toggle-btn ${!compareDryRun ? "active" : ""}`}
                  onClick={() => setCompareDryRun(false)}
                >
                  ✨ Live Gemini API
                </button>
              </div>
            </div>
          </div>

          {compareError && (
            <div className="dev-alert-danger">
              <span>⚠️</span>
              <span>{compareError}</span>
            </div>
          )}

          {/* Benchmark Delta Matrix */}
          {comparisonData && (
            <div className="results-visualizer">
              <div className="results-top-banner">
                <div className="results-title-group">
                  <span className="results-badge">Benchmark Matrix</span>
                  <h4 className="results-heading">
                    {comparisonData.prompt_a} (Baseline) vs. {comparisonData.prompt_b} (Candidate)
                  </h4>
                </div>
              </div>

              <div className="dev-card">
                <h4 className="card-heading">Comparative Performance Metrics</h4>
                <div className="dev-table-container">
                  <table className="dev-table compare-table">
                    <thead>
                      <tr>
                        <th>Metric</th>
                        <th>{comparisonData.prompt_a} (Baseline)</th>
                        <th>{comparisonData.prompt_b} (Candidate)</th>
                        <th>Delta Impact</th>
                      </tr>
                    </thead>
                    <tbody>
                      {comparisonData.metrics.map((m, idx) => (
                        <tr key={idx}>
                          <td className="metric-name-cell">{m.name}</td>
                          <td>{m.is_pct ? `${(m.val_a * 100).toFixed(1)}%` : m.val_a.toFixed(2)}</td>
                          <td>{m.is_pct ? `${(m.val_b * 100).toFixed(1)}%` : m.val_b.toFixed(2)}</td>
                          <td>
                            <span
                              className={`delta-tag ${
                                m.improved
                                  ? "delta-green"
                                  : m.status === "regressed"
                                  ? "delta-red"
                                  : "delta-gray"
                              }`}
                            >
                              {m.delta_str} {m.improved ? "▲ (Improved)" : m.status === "regressed" ? "▼ (Regressed)" : "—"}
                            </span>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Per-Tier F1 Comparison */}
              <div className="dev-card">
                <h4 className="card-heading">Per-Tier F1-Score Comparison</h4>
                <div className="dev-table-container">
                  <table className="dev-table">
                    <thead>
                      <tr>
                        <th>Priority Tier</th>
                        <th>{comparisonData.prompt_a} F1</th>
                        <th>{comparisonData.prompt_b} F1</th>
                        <th>Delta F1</th>
                      </tr>
                    </thead>
                    <tbody>
                      {Object.entries(comparisonData.tier_comparisons || {}).map(([tierKey, tc]) => {
                        const delta = tc.f1_b - tc.f1_a;
                        return (
                          <tr key={tierKey}>
                            <td>
                              <span className={`tier-badge-pill ${tierKey}`}>
                                {tierKey.replace("tier_", "").replace("_", " ").toUpperCase()}
                              </span>
                            </td>
                            <td>{tc.f1_a.toFixed(3)}</td>
                            <td><strong>{tc.f1_b.toFixed(3)}</strong></td>
                            <td>
                              <span className={`delta-tag ${delta >= 0 ? "delta-green" : "delta-red"}`}>
                                {delta >= 0 ? `+${delta.toFixed(3)} ▲` : `${delta.toFixed(3)} ▼`}
                              </span>
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          )}
        </div>
      )}

      {/* =================================================================== */}
      {/* VIEW 3: RUN HISTORY & LOGS                                         */}
      {/* =================================================================== */}
      {activeTab === "history-logs" && (() => {
        const totalHistoryPages = Math.ceil(historyItems.length / HISTORY_PAGE_SIZE) || 1;
        const currentSlice = historyItems.slice(
          (historyPage - 1) * HISTORY_PAGE_SIZE,
          historyPage * HISTORY_PAGE_SIZE
        );

        return (
          <div className="dev-page-section">
            <div className="dev-card">
              <div className="card-header-with-search">
                <h4 className="card-heading">Historical Evaluation Runs ({historyItems.length})</h4>
                <button className="btn-refresh" onClick={loadHistory} disabled={historyLoading}>
                  🔄 Refresh Logs
                </button>
              </div>

              {historyItems.length === 0 ? (
                <p className="empty-state-text">No evaluation history found. Run an evaluation above to record benchmarks.</p>
              ) : (
                <>
                  <div className="dev-table-container">
                    <table className="dev-table">
                      <thead>
                        <tr>
                          <th>Prompt Version</th>
                          <th>Accuracy</th>
                          <th>Macro F1</th>
                          <th>Score MAE</th>
                          <th>Within ±5 Pts</th>
                          <th>Timestamp</th>
                          <th>Action</th>
                        </tr>
                      </thead>
                      <tbody>
                        {currentSlice.map((item, idx) => {
                          const acc = typeof item.tier_accuracy === "number" ? formatPct(item.tier_accuracy) : "—";
                          const f1 = typeof item.macro_f1 === "number" ? item.macro_f1.toFixed(3) : "—";
                          const mae = typeof item.score_mae === "number" ? `${item.score_mae.toFixed(2)} pts` : "—";
                          const within5 = typeof item.within_5_points_pct === "number" ? `${item.within_5_points_pct.toFixed(1)}%` : "—";
                          let timeStr = "Recent";
                          if (item.timestamp) {
                            try {
                              const d = new Date(item.timestamp);
                              if (!isNaN(d.getTime())) {
                                timeStr = d.toLocaleString();
                              }
                            } catch {
                              timeStr = String(item.timestamp);
                            }
                          }

                          return (
                            <tr key={idx}>
                              <td>
                                <span className="prompt-chip">{item.prompt_version || "Unknown"}</span>
                              </td>
                              <td><strong>{acc}</strong></td>
                              <td>{f1}</td>
                              <td>{mae}</td>
                              <td>{within5}</td>
                              <td className="time-cell">{timeStr}</td>
                              <td>
                                <button
                                  type="button"
                                  className="btn-inspect"
                                  onClick={() => handleViewHistoricalResult(item.filename)}
                                >
                                  Inspect ↗
                                </button>
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>

                  {totalHistoryPages > 1 && (
                    <div className="table-pagination-bar">
                      <span className="pagination-info">
                        Showing {(historyPage - 1) * HISTORY_PAGE_SIZE + 1} – {Math.min(historyPage * HISTORY_PAGE_SIZE, historyItems.length)} of {historyItems.length} runs
                      </span>
                      <div className="pagination-controls">
                        <button
                          type="button"
                          className="btn-page"
                          disabled={historyPage === 1}
                          onClick={() => setHistoryPage((p) => Math.max(1, p - 1))}
                        >
                          ← Previous
                        </button>
                        <span className="page-indicator">
                          Page {historyPage} of {totalHistoryPages}
                        </span>
                        <button
                          type="button"
                          className="btn-page"
                          disabled={historyPage >= totalHistoryPages}
                          onClick={() => setHistoryPage((p) => Math.min(totalHistoryPages, p + 1))}
                        >
                          Next →
                        </button>
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        );
      })()}
    </div>
  );
};

export default DeveloperEvalPage;

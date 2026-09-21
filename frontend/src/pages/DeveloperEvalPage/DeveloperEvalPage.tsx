import React, { useState, useEffect, useRef } from "react";
import { api } from "../../api";
import { useAppStore } from "../../store";
import {
  PromptTemplateInfo,
  EvalResultData,
  EvalComparisonData,
  BackgroundJobSummary,
} from "../../types";
import "./DeveloperEvalPage.css";

interface Props {
  onBackToAccounts: () => void;
}

type DevPageTab = "single-run" | "benchmark-compare" | "prompt-management";

export const DeveloperEvalPage: React.FC<Props> = ({ onBackToAccounts }) => {
  const { currentUser, openProfileModal, openAuthModal } = useAppStore();
  const [activeTab, setActiveTab] = useState<DevPageTab>("single-run");

  // Prompts State
  const [prompts, setPrompts] = useState<PromptTemplateInfo[]>([]);
  const [loadingPrompts, setLoadingPrompts] = useState<boolean>(false);
  const [promptSearchFilter, setPromptSearchFilter] = useState<string>("");
  const [previewPrompt, setPreviewPrompt] = useState<PromptTemplateInfo | null>(null);
  const [copiedTemplate, setCopiedTemplate] = useState<boolean>(false);
  const [showCreatePrompt, setShowCreatePrompt] = useState<boolean>(false);
  const [showDiffViewer, setShowDiffViewer] = useState<boolean>(false);
  const [diffPromptA, setDiffPromptA] = useState<string>("v1.0");
  const [diffPromptB, setDiffPromptB] = useState<string>("v2.0");

  // New Prompt Form
  const [newPromptName, setNewPromptName] = useState<string>("account_scoring");
  const [newPromptVersion, setNewPromptVersion] = useState<string>("");
  const [newPromptType, setNewPromptType] = useState<string>("scoring");
  const [newPromptTemplate, setNewPromptTemplate] = useState<string>("");
  const [promptActionLoading, setPromptActionLoading] = useState<boolean>(false);
  const [promptActionMsg, setPromptActionMsg] = useState<{ type: "success" | "error"; text: string } | null>(null);

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

  // Background Jobs 3-Second Polling State for in-view runs
  const [evalJobProgress, setEvalJobProgress] = useState<{
    percent: number;
    current: number;
    total: number;
    status: string;
    jobId?: string;
  } | null>(null);
  const [compareJobProgress, setCompareJobProgress] = useState<{
    percent: number;
    current: number;
    total: number;
    status: string;
    jobId?: string;
  } | null>(null);

  const evalPollRef = useRef<any>(null);
  const comparePollRef = useRef<any>(null);

  // Dataset Configuration State
  const [datasetMode, setDatasetMode] = useState<"standard" | "subset" | "custom">("standard");
  const [defaultDataset, setDefaultDataset] = useState<any[]>([]);
  const [customDatasetJson, setCustomDatasetJson] = useState<string>("");
  const [sampleLimit, setSampleLimit] = useState<number>(5);
  const [datasetValidationMsg, setDatasetValidationMsg] = useState<{ type: "success" | "error" | "info"; text: string } | null>(null);

  // Jobs Queue State
  const [jobsList, setJobsList] = useState<BackgroundJobSummary[]>([]);
  const [loadingJobs, setLoadingJobs] = useState<boolean>(false);
  const [autoRefreshJobs, setAutoRefreshJobs] = useState<boolean>(true);
  const [copiedJobId, setCopiedJobId] = useState<string | null>(null);
  const [inspectingJobId, setInspectingJobId] = useState<string | null>(null);

  // Separate Filter & Search for Single and Compare Tables
  const [singleStatusFilter, setSingleStatusFilter] = useState<string>("all");
  const [singleSearchQuery, setSingleSearchQuery] = useState<string>("");

  const [compareStatusFilter, setCompareStatusFilter] = useState<string>("all");
  const [compareSearchQuery, setCompareSearchQuery] = useState<string>("");

  useEffect(() => {
    loadPrompts();
    loadDataset();
    loadEvalJobs();

    // Auto refresh evaluation jobs every 4 seconds
    const jobsInterval = setInterval(() => {
      if (autoRefreshJobs) {
        loadEvalJobs(true);
      }
    }, 4000);

    return () => {
      clearInterval(jobsInterval);
      if (evalPollRef.current) clearInterval(evalPollRef.current);
      if (comparePollRef.current) clearInterval(comparePollRef.current);
    };
  }, [autoRefreshJobs]);

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
    setLoadingPrompts(true);
    try {
      const data = await api.listPrompts();
      if (data && data.prompts) {
        setPrompts(data.prompts);
        const scoringV2 = data.prompts.find((p) => p.version === "v2.0" || p.name.includes("v2.0"));
        if (scoringV2) {
          setCustomPrompt(scoringV2.template);
          if (!previewPrompt) {
            setPreviewPrompt(scoringV2);
          }
        } else if (data.prompts.length > 0) {
          setCustomPrompt(data.prompts[0].template);
          if (!previewPrompt) {
            setPreviewPrompt(data.prompts[0]);
          }
        }
      }
    } catch (err) {
      console.warn("Failed to load prompts from /prompts:", err);
      // Fallback to /eval/prompts
      try {
        const evalPromptData = await api.getEvalPrompts();
        if (evalPromptData && evalPromptData.prompts) {
          setPrompts(evalPromptData.prompts);
        }
      } catch (fallbackErr) {
        console.warn("Failed fallback prompts:", fallbackErr);
      }
    } finally {
      setLoadingPrompts(false);
    }
  };

  const loadEvalJobs = async (silent = false) => {
    if (!silent) setLoadingJobs(true);
    try {
      const data = await api.listJobs({ limit: 100 });
      if (data && data.items) {
        const evalJobs = data.items.filter(
          (j) => j.job_type === "eval_run" || j.job_type === "eval_compare" || j.job_type.startsWith("eval_")
        );
        setJobsList(evalJobs);
      }
    } catch (err) {
      console.warn("Failed to load background evaluation jobs:", err);
    } finally {
      if (!silent) setLoadingJobs(false);
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

    if (evalPollRef.current) {
      clearInterval(evalPollRef.current);
      evalPollRef.current = null;
    }

    setEvalLoading(true);
    setEvalError(null);
    setEvalJobProgress(null);

    try {
      const resp = await api.runEval({
        prompt_version: isCustomPrompt ? "custom" : selectedPrompt,
        custom_prompt_template: isCustomPrompt ? customPrompt : undefined,
        dry_run: dryRun,
        eval_set: datasetParams.eval_set,
        sample_limit: datasetParams.sample_limit,
      });

      if (resp && resp.job_id) {
        const totalCases = datasetParams.eval_set?.length || datasetParams.sample_limit || 25;
        
        // Optimistically add job to local table so it appears immediately
        const optimisticJob: BackgroundJobSummary = {
          job_id: resp.job_id,
          job_type: "eval_run",
          status: "running",
          title: `Single Eval (${isCustomPrompt ? "custom" : selectedPrompt})`,
          progress_current: 0,
          progress_total: totalCases,
          progress_percent: 0,
          retry_count: 0,
          max_retries: 3,
          metadata: {
            prompt_version: isCustomPrompt ? "custom" : selectedPrompt,
            dry_run: dryRun,
            sample_limit: datasetParams.sample_limit,
          },
          created_at: new Date().toISOString(),
        };
        setJobsList((prev) => [optimisticJob, ...prev.filter((j) => j.job_id !== resp.job_id)]);
        loadEvalJobs(true);

        setEvalJobProgress({
          percent: 0,
          current: 0,
          total: totalCases,
          status: "running",
          jobId: resp.job_id,
        });

        // Poll every 3 seconds
        evalPollRef.current = setInterval(async () => {
          try {
            const job = await api.getJob(resp.job_id);
            if (!job) return;

            const progressPct = job.progress_percent ?? Math.round(((job.progress_current || 0) / (job.progress_total || 1)) * 100);
            setEvalJobProgress({
              percent: Math.min(100, progressPct),
              current: job.progress_current || 0,
              total: job.progress_total || totalCases,
              status: job.status,
              jobId: resp.job_id,
            });

            // Update row in table in real-time
            setJobsList((prev) =>
              prev.map((j) =>
                j.job_id === resp.job_id
                  ? {
                      ...j,
                      status: job.status,
                      progress_current: job.progress_current || 0,
                      progress_total: job.progress_total || totalCases,
                      progress_percent: Math.min(100, progressPct),
                      metadata: { ...j.metadata, ...job.metadata },
                      error_message: job.error_message,
                    }
                  : j
              )
            );

            if (job.status === "completed") {
              if (evalPollRef.current) clearInterval(evalPollRef.current);
              evalPollRef.current = null;

              const payload = job.results;
              const actualResults = payload?.results?.results || payload?.results || payload;
              if (actualResults && actualResults.predictions) {
                setEvalResult(actualResults);
              } else if (actualResults) {
                setEvalResult(actualResults);
              }
              loadEvalJobs(true);
              setEvalLoading(false);
            } else if (job.status === "failed" || job.status === "cancelled") {
              if (evalPollRef.current) clearInterval(evalPollRef.current);
              evalPollRef.current = null;
              setEvalError(job.error_message || "Evaluation background job failed");
              loadEvalJobs(true);
              setEvalLoading(false);
            }
          } catch (pollErr: any) {
            console.warn("Polling eval job error:", pollErr);
          }
        }, 3000);
      } else if (resp && resp.results) {
        setEvalResult(resp.results);
        loadEvalJobs(true);
        setEvalLoading(false);
      } else {
        throw new Error("Invalid response format from eval runner");
      }
    } catch (err: any) {
      if (evalPollRef.current) clearInterval(evalPollRef.current);
      evalPollRef.current = null;
      const detail = err.response?.data?.detail || err.message || "Evaluation execution failed";
      setEvalError(detail);
      setEvalLoading(false);
      if (err.response?.status === 401) {
        openAuthModal("signin");
      } else if (err.response?.status === 400 && detail.includes("API key")) {
        openProfileModal();
      }
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

    if (comparePollRef.current) {
      clearInterval(comparePollRef.current);
      comparePollRef.current = null;
    }

    setCompareLoading(true);
    setCompareError(null);
    setCompareJobProgress(null);

    try {
      const resp = await api.compareEval({
        prompt_a: comparePromptA,
        prompt_b: comparePromptB,
        dry_run: compareDryRun,
        eval_set: datasetParams.eval_set,
        sample_limit: datasetParams.sample_limit,
      });

      if (resp && resp.job_id) {
        const singleCases = datasetParams.eval_set?.length || datasetParams.sample_limit || 25;
        const totalCases = 2 * singleCases;

        // Optimistically add job to local table so it appears immediately
        const optimisticJob: BackgroundJobSummary = {
          job_id: resp.job_id,
          job_type: "eval_compare",
          status: "running",
          title: `Compare (${comparePromptA} vs ${comparePromptB})`,
          progress_current: 0,
          progress_total: totalCases,
          progress_percent: 0,
          retry_count: 0,
          max_retries: 3,
          metadata: {
            prompt_a: comparePromptA,
            prompt_b: comparePromptB,
            dry_run: compareDryRun,
            sample_limit: datasetParams.sample_limit,
          },
          created_at: new Date().toISOString(),
        };
        setJobsList((prev) => [optimisticJob, ...prev.filter((j) => j.job_id !== resp.job_id)]);
        loadEvalJobs(true);

        setCompareJobProgress({
          percent: 0,
          current: 0,
          total: totalCases,
          status: "running",
          jobId: resp.job_id,
        });

        // Poll every 3 seconds
        comparePollRef.current = setInterval(async () => {
          try {
            const job = await api.getJob(resp.job_id);
            if (!job) return;

            const progressPct = job.progress_percent ?? Math.round(((job.progress_current || 0) / (job.progress_total || 1)) * 100);
            setCompareJobProgress({
              percent: Math.min(100, progressPct),
              current: job.progress_current || 0,
              total: job.progress_total || totalCases,
              status: job.status,
              jobId: resp.job_id,
            });

            // Update row in table in real-time
            setJobsList((prev) =>
              prev.map((j) =>
                j.job_id === resp.job_id
                  ? {
                      ...j,
                      status: job.status,
                      progress_current: job.progress_current || 0,
                      progress_total: job.progress_total || totalCases,
                      progress_percent: Math.min(100, progressPct),
                      metadata: { ...j.metadata, ...job.metadata },
                      error_message: job.error_message,
                    }
                  : j
              )
            );

            if (job.status === "completed") {
              if (comparePollRef.current) clearInterval(comparePollRef.current);
              comparePollRef.current = null;

              const payload = job.results;
              const actualData = payload?.results?.comparison || payload?.comparison || payload?.results || payload;
              if (actualData && (actualData.metrics || actualData.tier_comparisons)) {
                setComparisonData(actualData);
              }
              loadEvalJobs(true);
              setCompareLoading(false);
            } else if (job.status === "failed" || job.status === "cancelled") {
              if (comparePollRef.current) clearInterval(comparePollRef.current);
              comparePollRef.current = null;
              setCompareError(job.error_message || "Benchmark comparison job failed");
              loadEvalJobs(true);
              setCompareLoading(false);
            }
          } catch (pollErr: any) {
            console.warn("Polling compare job error:", pollErr);
          }
        }, 3000);
      } else if (resp && resp.comparison) {
        setComparisonData(resp.comparison);
        loadEvalJobs(true);
        setCompareLoading(false);
      } else {
        throw new Error("Invalid response from comparison runner");
      }
    } catch (err: any) {
      if (comparePollRef.current) clearInterval(comparePollRef.current);
      comparePollRef.current = null;
      const detail = err.response?.data?.detail || err.message || "Benchmark comparison failed";
      setCompareError(detail);
      setCompareLoading(false);
      if (err.response?.status === 401) {
        openAuthModal("signin");
      } else if (err.response?.status === 400 && detail.includes("API key")) {
        openProfileModal();
      }
    }
  };

  const handleInspectJob = async (job: BackgroundJobSummary) => {
    setInspectingJobId(job.job_id);
    try {
      const detail = await api.getJob(job.job_id);
      if (!detail) return;

      if (detail.job_type === "eval_run") {
        const payload = detail.results;
        const actualResults = payload?.results?.results || payload?.results || payload;
        if (actualResults && actualResults.predictions) {
          setEvalResult(actualResults);
          setActiveTab("single-run");
          setTimeout(() => {
            const resEl = document.querySelector(".results-visualizer");
            if (resEl) {
              resEl.scrollIntoView({ behavior: "smooth" });
            } else {
              window.scrollTo({ top: 380, behavior: "smooth" });
            }
          }, 100);
        } else if (actualResults) {
          setEvalResult(actualResults);
          setActiveTab("single-run");
        }
      } else if (detail.job_type === "eval_compare") {
        const payload = detail.results;
        const actualData = payload?.results?.comparison || payload?.comparison || payload?.results || payload;
        if (actualData && (actualData.metrics || actualData.tier_comparisons)) {
          setComparisonData(actualData);
          setActiveTab("benchmark-compare");
          setTimeout(() => {
            const resEl = document.querySelector(".results-visualizer");
            if (resEl) {
              resEl.scrollIntoView({ behavior: "smooth" });
            } else {
              window.scrollTo({ top: 380, behavior: "smooth" });
            }
          }, 100);
        }
      }
    } catch (err: any) {
      console.error("Failed to inspect eval job:", err);
    } finally {
      setInspectingJobId(null);
    }
  };

  // Prompt Management Handlers
  const handleRegisterPrompt = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newPromptVersion.trim()) {
      setPromptActionMsg({ type: "error", text: "Prompt version identifier is required (e.g. v2.1-custom)." });
      return;
    }
    if (!newPromptTemplate.trim()) {
      setPromptActionMsg({ type: "error", text: "Prompt template instructions cannot be empty." });
      return;
    }
    if (!newPromptTemplate.includes("{account_context}")) {
      setPromptActionMsg({ type: "error", text: "Prompt template must contain the placeholder: {account_context}" });
      return;
    }

    setPromptActionLoading(true);
    setPromptActionMsg(null);
    try {
      await api.registerPrompt({
        name: newPromptName.trim() || "account_scoring",
        version: newPromptVersion.trim(),
        prompt_type: newPromptType,
        template: newPromptTemplate,
      });
      setPromptActionMsg({ type: "success", text: `✓ Successfully registered prompt '${newPromptVersion}'.` });
      setShowCreatePrompt(false);
      setNewPromptVersion("");
      setNewPromptTemplate("");
      await loadPrompts();
    } catch (err: any) {
      const msg = err.response?.data?.error?.message || err.userMessage || err.message || "Failed to register prompt";
      setPromptActionMsg({ type: "error", text: msg });
    } finally {
      setPromptActionLoading(false);
    }
  };

  const handleDeletePrompt = async (prompt: PromptTemplateInfo) => {
    if (prompt.version === "v1.0" || prompt.version === "v2.0") {
      alert("Built-in canonical prompt versions (v1.0 and v2.0) cannot be deleted.");
      return;
    }
    const confirmed = window.confirm(
      `Are you sure you want to permanently delete prompt version '${prompt.version}' (${prompt.name})?`
    );
    if (!confirmed) return;

    setPromptActionLoading(true);
    try {
      await api.deletePrompt(prompt.name, prompt.version);
      if (previewPrompt?.version === prompt.version) {
        setPreviewPrompt(null);
      }
      setPromptActionMsg({ type: "success", text: `Deleted prompt version '${prompt.version}'.` });
      await loadPrompts();
    } catch (err: any) {
      const msg = err.response?.data?.error?.message || err.userMessage || err.message || "Failed to delete prompt";
      setPromptActionMsg({ type: "error", text: msg });
    } finally {
      setPromptActionLoading(false);
    }
  };

  const handleCopyTemplate = (text: string) => {
    navigator.clipboard.writeText(text);
    setCopiedTemplate(true);
    setTimeout(() => setCopiedTemplate(false), 2000);
  };

  const handleCopyJobId = (e: React.MouseEvent, id: string) => {
    e.stopPropagation();
    navigator.clipboard.writeText(id);
    setCopiedJobId(id);
    setTimeout(() => setCopiedJobId(null), 2000);
  };

  const formatPct = (val?: number | null) =>
    typeof val === "number" && !isNaN(val) ? `${(val * 100).toFixed(1)}%` : "—";

  const formatTime = (ts?: string | null) => {
    if (!ts) return "—";
    try {
      const d = new Date(ts);
      if (!isNaN(d.getTime())) {
        return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) + ' · ' + d.toLocaleDateString();
      }
    } catch {
      return String(ts);
    }
    return String(ts);
  };

  // Diff computation helper between two prompt texts
  const computeLineDiff = (textA: string, textB: string) => {
    const linesA = textA.split("\n");
    const linesB = textB.split("\n");
    const maxLen = Math.max(linesA.length, linesB.length);
    const rows = [];
    for (let i = 0; i < maxLen; i++) {
      const lineA = linesA[i] !== undefined ? linesA[i] : null;
      const lineB = linesB[i] !== undefined ? linesB[i] : null;
      let status: "same" | "changed" | "added" | "removed" = "same";
      if (lineA === null && lineB !== null) {
        status = "added";
      } else if (lineA !== null && lineB === null) {
        status = "removed";
      } else if (lineA !== lineB) {
        status = "changed";
      }
      rows.push({
        lineNum: i + 1,
        lineA,
        lineB,
        status,
      });
    }
    return rows;
  };

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

  // Filtered Prompts List
  const filteredPrompts = prompts.filter((p) => {
    if (!promptSearchFilter.trim()) return true;
    const q = promptSearchFilter.toLowerCase();
    return (
      p.name.toLowerCase().includes(q) ||
      p.version.toLowerCase().includes(q) ||
      (p.type || "").toLowerCase().includes(q) ||
      p.template.toLowerCase().includes(q)
    );
  });

  // Prompt Diff calculation
  const promptItemA = prompts.find((p) => p.version === diffPromptA) || prompts[0];
  const promptItemB = prompts.find((p) => p.version === diffPromptB) || prompts[1] || prompts[0];
  const diffRows = promptItemA && promptItemB ? computeLineDiff(promptItemA.template, promptItemB.template) : [];

  // Jobs counts by category
  const singleJobsList = jobsList.filter((j) => j.job_type === "eval_run");
  const compareJobsList = jobsList.filter((j) => j.job_type === "eval_compare");

  const singleRunningCount = singleJobsList.filter((j) => j.status === "running").length;
  const singleQueuedCount = singleJobsList.filter((j) => j.status === "queued").length;
  const singleCompletedCount = singleJobsList.filter((j) => j.status === "completed").length;
  const singleFailedCount = singleJobsList.filter((j) => j.status === "failed" || j.status === "cancelled").length;

  const compareRunningCount = compareJobsList.filter((j) => j.status === "running").length;
  const compareQueuedCount = compareJobsList.filter((j) => j.status === "queued").length;
  const compareCompletedCount = compareJobsList.filter((j) => j.status === "completed").length;
  const compareFailedCount = compareJobsList.filter((j) => j.status === "failed" || j.status === "cancelled").length;

  const totalActiveJobs = jobsList.filter((j) => j.status === "running" || j.status === "queued").length;

  // Filtered lists for each table
  const filteredSingleJobs = singleJobsList.filter((j) => {
    if (singleStatusFilter === "running" && j.status !== "running") return false;
    if (singleStatusFilter === "queued" && j.status !== "queued") return false;
    if (singleStatusFilter === "completed" && j.status !== "completed") return false;
    if (singleStatusFilter === "failed" && j.status !== "failed" && j.status !== "cancelled") return false;

    if (singleSearchQuery.trim()) {
      const q = singleSearchQuery.toLowerCase();
      const titleMatch = (j.title || "").toLowerCase().includes(q);
      const idMatch = (j.job_id || "").toLowerCase().includes(q);
      const promptMatch = (j.metadata?.prompt_version || "").toLowerCase().includes(q);
      return titleMatch || idMatch || promptMatch;
    }
    return true;
  });

  const filteredCompareJobs = compareJobsList.filter((j) => {
    if (compareStatusFilter === "running" && j.status !== "running") return false;
    if (compareStatusFilter === "queued" && j.status !== "queued") return false;
    if (compareStatusFilter === "completed" && j.status !== "completed") return false;
    if (compareStatusFilter === "failed" && j.status !== "failed" && j.status !== "cancelled") return false;

    if (compareSearchQuery.trim()) {
      const q = compareSearchQuery.toLowerCase();
      const titleMatch = (j.title || "").toLowerCase().includes(q);
      const idMatch = (j.job_id || "").toLowerCase().includes(q);
      const promptMatch =
        (j.metadata?.prompt_a || "").toLowerCase().includes(q) ||
        (j.metadata?.prompt_b || "").toLowerCase().includes(q);
      return titleMatch || idMatch || promptMatch;
    }
    return true;
  });

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
            Test prompt revisions against hand-labeled cybersecurity ground truth data (<code>eval_v1.json</code>), manage system prompt versions, preview markdown instructions, compare prompt diffs, and execute parallel background benchmark jobs.
          </p>
        </div>

        <div className="dev-hero-stats">
          <div className="hero-stat-box">
            <span className="hero-stat-label">Prompt Versions</span>
            <span className="hero-stat-val">{prompts.length} Registered</span>
          </div>
          <div className="hero-stat-box">
            <span className="hero-stat-label">Active Jobs</span>
            <span className="hero-stat-val text-primary-val">{totalActiveJobs}</span>
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
          {singleRunningCount + singleQueuedCount > 0 && (
            <span className="tab-active-pulse-badge">
              <span className="pulse-dot" />
              {singleRunningCount + singleQueuedCount} Active
            </span>
          )}
        </button>

        <button
          type="button"
          className={`dev-page-tab-btn ${activeTab === "benchmark-compare" ? "active" : ""}`}
          onClick={() => setActiveTab("benchmark-compare")}
        >
          <span>⚖️</span>
          <span>Prompt Benchmark Comparison</span>
          {compareRunningCount + compareQueuedCount > 0 && (
            <span className="tab-active-pulse-badge">
              <span className="pulse-dot" />
              {compareRunningCount + compareQueuedCount} Active
            </span>
          )}
        </button>

        <button
          type="button"
          className={`dev-page-tab-btn ${activeTab === "prompt-management" ? "active" : ""}`}
          onClick={() => setActiveTab("prompt-management")}
        >
          <span>📝</span>
          <span>Prompt Management</span>
          <span className="tab-count-badge">{prompts.length}</span>
        </button>
      </div>

      {/* =================================================================== */}
      {/* VIEW 1: SINGLE EVALUATION RUN                                      */}
      {/* =================================================================== */}
      {activeTab === "single-run" && (
        <div className="dev-page-section">
          {/* Section 1: Configuration */}
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
                  {prompts.map((p) => (
                    <option key={p.version} value={p.version}>
                      {p.version} {p.version === "v2.0" ? "(Calibrated - Production)" : p.version === "v1.0" ? "(Baseline Initial)" : `(${p.name})`}
                    </option>
                  ))}
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
                      setDatasetValidationMsg(null);
                    }}
                  >
                    🛠️ Custom JSON
                  </button>
                </div>
              </div>

              {datasetMode === "subset" && (
                <div className="dataset-subset-controls">
                  <span className="subset-label">Select Sample Size:</span>
                  <div className="subset-pills-row">
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
                  </div>
                  <span className="subset-hint">⚡ Evaluated in parallel workers with 3s live polling</span>
                </div>
              )}

              {datasetMode === "custom" && (
                <div className="custom-dataset-editor-wrap">
                  <div className="dataset-editor-toolbar">
                    <div className="editor-tools-left">
                      <button
                        type="button"
                        className="btn-toolbar-action"
                        onClick={() => {
                          try {
                            validateCustomDataset();
                          } catch {
                            // Handled in validate
                          }
                        }}
                      >
                        ✓ Validate Schema
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
                    <span>Running Evaluation Background Job...</span>
                  </>
                ) : (
                  <>
                    <span>🚀</span>
                    <span>Run Evaluation ({datasetMode === "subset" ? `${sampleLimit} Samples` : datasetMode === "custom" ? "Custom Set" : `${defaultDataset.length || 25} Ground Truth`})</span>
                  </>
                )}
              </button>
            </div>

            {evalLoading && evalJobProgress && (
              <div className="eval-job-progress-card">
                <div className="eval-job-meta-row">
                  <div className="eval-job-title-group">
                    <span className="page-spinner" />
                    <span>⚡ Parallel Evaluation Worker</span>
                  </div>
                  <span className="eval-polling-badge">
                    🔄 Polling (every 3s) · {evalJobProgress.status.toUpperCase()}
                  </span>
                </div>
                <div className="eval-progress-bar-wrap">
                  <div
                    className="eval-progress-bar-fill"
                    style={{ width: `${Math.max(5, evalJobProgress.percent)}%` }}
                  />
                </div>
                <div className="eval-progress-stats-row">
                  <span>Processed {evalJobProgress.current} of {evalJobProgress.total} test cases</span>
                  <span>{evalJobProgress.percent}% Complete</span>
                </div>
              </div>
            )}
          </div>

          {evalError && (
            <div className="dev-alert-danger">
              <span>⚠️</span>
              <span>{evalError}</span>
            </div>
          )}

          {/* Dedicated Single Evaluation Jobs Queue Table */}
          <div className="dev-card jobs-queue-card">
            <div className="jobs-queue-header">
              <div className="jobs-header-left">
                <h3 className="section-title">Single Prompt Evaluation Queue &amp; Recent Runs</h3>
                <p className="jobs-header-desc">
                  Real-time parallel evaluation jobs for single prompt benchmarks. As jobs are submitted, live progress is previewed below. Click <strong>Inspect ↗</strong> to load full scorecards.
                </p>
              </div>

              <div className="jobs-header-actions">
                <button
                  type="button"
                  className={`btn-auto-refresh-toggle ${autoRefreshJobs ? "active" : ""}`}
                  onClick={() => setAutoRefreshJobs(!autoRefreshJobs)}
                  title="Toggle automatic 4-second status polling"
                >
                  <span className={`refresh-indicator ${autoRefreshJobs ? "spin" : ""}`}>⟳</span>
                  <span>Auto-Refresh: {autoRefreshJobs ? "ON" : "OFF"}</span>
                </button>

                <button
                  type="button"
                  className="btn-refresh-manual"
                  onClick={() => loadEvalJobs(false)}
                  disabled={loadingJobs}
                >
                  {loadingJobs ? <span className="page-spinner" /> : "🔄"}
                  <span>Sync Status</span>
                </button>
              </div>
            </div>

            {/* Filter Pills and Search */}
            <div className="jobs-filter-bar">
              <div className="job-status-filter-pills">
                <button
                  type="button"
                  className={`status-filter-pill ${singleStatusFilter === "all" ? "active" : ""}`}
                  onClick={() => setSingleStatusFilter("all")}
                >
                  <span>All</span>
                  <span className="pill-count">{singleJobsList.length}</span>
                </button>

                <button
                  type="button"
                  className={`status-filter-pill filter-running ${singleStatusFilter === "running" ? "active" : ""}`}
                  onClick={() => setSingleStatusFilter("running")}
                >
                  <span className="status-dot dot-running" />
                  <span>In Progress</span>
                  <span className="pill-count">{singleRunningCount}</span>
                </button>

                <button
                  type="button"
                  className={`status-filter-pill filter-queued ${singleStatusFilter === "queued" ? "active" : ""}`}
                  onClick={() => setSingleStatusFilter("queued")}
                >
                  <span className="status-dot dot-queued" />
                  <span>Pending</span>
                  <span className="pill-count">{singleQueuedCount}</span>
                </button>

                <button
                  type="button"
                  className={`status-filter-pill filter-completed ${singleStatusFilter === "completed" ? "active" : ""}`}
                  onClick={() => setSingleStatusFilter("completed")}
                >
                  <span className="status-dot dot-completed" />
                  <span>Completed</span>
                  <span className="pill-count">{singleCompletedCount}</span>
                </button>

                <button
                  type="button"
                  className={`status-filter-pill filter-failed ${singleStatusFilter === "failed" ? "active" : ""}`}
                  onClick={() => setSingleStatusFilter("failed")}
                >
                  <span className="status-dot dot-failed" />
                  <span>Failed</span>
                  <span className="pill-count">{singleFailedCount}</span>
                </button>
              </div>

              <div className="job-search-box">
                <input
                  type="text"
                  className="job-search-input"
                  placeholder="Search by Job ID or prompt version..."
                  value={singleSearchQuery}
                  onChange={(e) => setSingleSearchQuery(e.target.value)}
                />
                {singleSearchQuery && (
                  <button className="btn-clear-search" onClick={() => setSingleSearchQuery("")}>
                    ✕
                  </button>
                )}
              </div>
            </div>

            {/* Table Content */}
            {filteredSingleJobs.length === 0 ? (
              <div className="jobs-empty-state">
                <div className="empty-icon">📭</div>
                <h4 className="empty-title">
                  {singleJobsList.length === 0 ? "No Single Evaluation Jobs Yet" : "No Jobs Match Selected Filter"}
                </h4>
                <p className="empty-subtitle">
                  {singleJobsList.length === 0
                    ? "Click 'Run Evaluation' above to submit an asynchronous benchmark job."
                    : "Try selecting 'All' or clearing your search query."}
                </p>
              </div>
            ) : (
              <div className="dev-table-container">
                <table className="dev-table jobs-queue-table">
                  <thead>
                    <tr>
                      <th>Job ID</th>
                      <th>Target Prompt</th>
                      <th>Mode</th>
                      <th>Status</th>
                      <th>Progress</th>
                      <th>Accuracy / Metrics</th>
                      <th>Submitted At</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredSingleJobs.map((job) => {
                      const isRunning = job.status === "running";
                      const isQueued = job.status === "queued";
                      const isCompleted = job.status === "completed";
                      const isFailed = job.status === "failed" || job.status === "cancelled";
                      const pct =
                        job.progress_percent ??
                        Math.round(((job.progress_current || 0) / (job.progress_total || 1)) * 100);

                      const promptLabel = job.metadata?.prompt_version || "v2.0";
                      const isDry = job.metadata?.dry_run !== false;

                      return (
                        <tr key={job.job_id} className={`job-row status-${job.status}`}>
                          {/* Job ID */}
                          <td className="table-id-cell">
                            <span
                              className="table-id-chip"
                              onClick={(e) => handleCopyJobId(e, job.job_id)}
                              title="Click to copy full Job ID"
                            >
                              <code>{job.job_id.slice(0, 8)}...</code>
                              <span className="copy-icon">
                                {copiedJobId === job.job_id ? "✓" : "📋"}
                              </span>
                            </span>
                          </td>

                          {/* Target Prompt */}
                          <td className="table-target-cell">
                            <code className="target-prompt-code">{promptLabel}</code>
                          </td>

                          {/* Mode */}
                          <td>
                            <span className={`job-mode-pill ${isDry ? "mode-dry" : "mode-live"}`}>
                              {isDry ? "⚡ Dry-Run" : "✨ Live"}
                            </span>
                          </td>

                          {/* Status */}
                          <td>
                            <span className={`status-badge-chip badge-${job.status}`}>
                              {isRunning && <span className="status-spinner-small" />}
                              {isQueued && "⏳ "}
                              {isCompleted && "✓ "}
                              {isFailed && "❌ "}
                              {job.status.toUpperCase()}
                            </span>
                          </td>

                          {/* Progress */}
                          <td className="table-progress-cell">
                            {isCompleted ? (
                              <span className="text-green-pct">100% ({job.progress_total || "All"} Cases)</span>
                            ) : (
                              <div className="table-mini-progress">
                                <div className="table-mini-bar-wrap">
                                  <div
                                    className={`table-mini-bar-fill ${isRunning ? "active" : ""}`}
                                    style={{ width: `${Math.max(5, Math.min(100, pct))}%` }}
                                  />
                                </div>
                                <span className="table-mini-progress-label">
                                  {pct}% ({job.progress_current || 0}/{job.progress_total || 1})
                                </span>
                              </div>
                            )}
                          </td>

                          {/* Metrics / Output */}
                          <td className="table-metrics-cell">
                            {isCompleted && job.metadata?.tier_accuracy !== undefined ? (
                              <span className="metric-tag accuracy-tag">
                                Accuracy: <strong>{formatPct(job.metadata.tier_accuracy)}</strong>
                              </span>
                            ) : isCompleted ? (
                              <span className="metric-tag completed-tag">Results Ready</span>
                            ) : isFailed ? (
                              <span className="metric-tag error-tag" title={job.error_message || "Failed"}>
                                ⚠️ {job.error_message ? job.error_message.slice(0, 30) + "..." : "Error"}
                              </span>
                            ) : (
                              <span className="metric-tag queued-tag">
                                {isRunning ? "Evaluating cases..." : "Queued"}
                              </span>
                            )}
                          </td>

                          {/* Submitted At */}
                          <td className="time-cell" title={job.created_at || ""}>
                            {formatTime(job.created_at)}
                          </td>

                          {/* Actions */}
                          <td className="table-action-cell">
                            {isCompleted ? (
                              <button
                                type="button"
                                className="btn-inspect"
                                onClick={() => handleInspectJob(job)}
                                disabled={inspectingJobId === job.job_id}
                              >
                                {inspectingJobId === job.job_id ? "Loading..." : "Inspect ↗"}
                              </button>
                            ) : isRunning ? (
                              <span className="running-live-tag">
                                <span className="status-spinner-small" /> Live
                              </span>
                            ) : (
                              <span className="table-idle-text">—</span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>

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
          {/* Section 1: Comparison Parameters */}
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
                  {prompts.map((p) => (
                    <option key={p.version} value={p.version}>
                      {p.version} {p.version === "v1.0" ? "(Baseline Initial)" : p.version === "v2.0" ? "(Calibrated)" : `(${p.name})`}
                    </option>
                  ))}
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
                  {prompts.map((p) => (
                    <option key={p.version} value={p.version}>
                      {p.version} {p.version === "v2.0" ? "(Calibrated - Production)" : p.version === "v1.0" ? "(Baseline Initial)" : `(${p.name})`}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <div className="config-row-grid" style={{ marginTop: "16px" }}>
              <div className="config-field">
                <label className="field-label">Execution Strategy</label>
                <div className="mode-toggle-group">
                  <button
                    type="button"
                    className={`toggle-btn ${compareDryRun ? "active" : ""}`}
                    onClick={() => setCompareDryRun(true)}
                  >
                    ⚡ Fast Dry-Run (Heuristic · 0 Quota)
                  </button>
                  <button
                    type="button"
                    className={`toggle-btn ${!compareDryRun ? "active" : ""}`}
                    onClick={() => setCompareDryRun(false)}
                  >
                    ✨ Live Gemini API ({currentUser?.has_api_key ? "Personal Key" : "System Quota"})
                  </button>
                </div>
              </div>
            </div>

            {/* Evaluation Dataset Configuration Card for Compare */}
            <div className="dataset-config-box">
              <div className="dataset-config-header">
                <div className="dataset-header-title">
                  <span className="dataset-icon">📊</span>
                  <div>
                    <div className="dataset-title-text">Evaluation Benchmark Dataset</div>
                    <div className="dataset-subtitle-text">
                      Choose standard ground truth or a fast sample subset for side-by-side comparison.
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
                      setDatasetValidationMsg(null);
                    }}
                  >
                    🛠️ Custom JSON
                  </button>
                </div>
              </div>

              {datasetMode === "subset" && (
                <div className="dataset-subset-controls">
                  <span className="subset-label">Select Sample Size:</span>
                  <div className="subset-pills-row">
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
                  </div>
                  <span className="subset-hint">⚡ Both prompts evaluated in parallel workers</span>
                </div>
              )}

              {datasetMode === "custom" && (
                <div className="custom-dataset-editor-wrap">
                  <div className="dataset-editor-toolbar">
                    <div className="editor-tools-left">
                      <button
                        type="button"
                        className="btn-toolbar-action"
                        onClick={() => {
                          try {
                            validateCustomDataset();
                          } catch {
                            // Handled in validate
                          }
                        }}
                      >
                        ✓ Validate Schema
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
                    rows={6}
                    value={customDatasetJson}
                    onChange={(e) => {
                      setCustomDatasetJson(e.target.value);
                      setDatasetValidationMsg(null);
                    }}
                    placeholder='[ ... ]'
                  />
                </div>
              )}
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
                    <span>Running Comparison Background Job...</span>
                  </>
                ) : (
                  <>
                    <span>⚖️</span>
                    <span>Run Comparison Benchmark ({comparePromptA} vs {comparePromptB})</span>
                  </>
                )}
              </button>
            </div>

            {compareLoading && compareJobProgress && (
              <div className="eval-job-progress-card">
                <div className="eval-job-meta-row">
                  <div className="eval-job-title-group">
                    <span className="page-spinner" />
                    <span>⚡ Parallel Comparison Workers</span>
                  </div>
                  <span className="eval-polling-badge">
                    🔄 Polling (every 3s) · {compareJobProgress.status.toUpperCase()}
                  </span>
                </div>
                <div className="eval-progress-bar-wrap">
                  <div
                    className="eval-progress-bar-fill"
                    style={{ width: `${Math.max(5, compareJobProgress.percent)}%` }}
                  />
                </div>
                <div className="eval-progress-stats-row">
                  <span>Processed {compareJobProgress.current} of {compareJobProgress.total} dual test evaluations</span>
                  <span>{compareJobProgress.percent}% Complete</span>
                </div>
              </div>
            )}
          </div>

          {compareError && (
            <div className="dev-alert-danger">
              <span>⚠️</span>
              <span>{compareError}</span>
            </div>
          )}

          {/* Dedicated Prompt Benchmark Comparison Jobs Queue Table */}
          <div className="dev-card jobs-queue-card">
            <div className="jobs-queue-header">
              <div className="jobs-header-left">
                <h3 className="section-title">Prompt Benchmark Comparison Queue &amp; Recent Runs</h3>
                <p className="jobs-header-desc">
                  Real-time side-by-side prompt comparison jobs. As comparisons run in parallel, live progress is previewed below. Click <strong>Inspect ↗</strong> to view delta matrices.
                </p>
              </div>

              <div className="jobs-header-actions">
                <button
                  type="button"
                  className={`btn-auto-refresh-toggle ${autoRefreshJobs ? "active" : ""}`}
                  onClick={() => setAutoRefreshJobs(!autoRefreshJobs)}
                  title="Toggle automatic 4-second status polling"
                >
                  <span className={`refresh-indicator ${autoRefreshJobs ? "spin" : ""}`}>⟳</span>
                  <span>Auto-Refresh: {autoRefreshJobs ? "ON" : "OFF"}</span>
                </button>

                <button
                  type="button"
                  className="btn-refresh-manual"
                  onClick={() => loadEvalJobs(false)}
                  disabled={loadingJobs}
                >
                  {loadingJobs ? <span className="page-spinner" /> : "🔄"}
                  <span>Sync Status</span>
                </button>
              </div>
            </div>

            {/* Filter Pills and Search */}
            <div className="jobs-filter-bar">
              <div className="job-status-filter-pills">
                <button
                  type="button"
                  className={`status-filter-pill ${compareStatusFilter === "all" ? "active" : ""}`}
                  onClick={() => setCompareStatusFilter("all")}
                >
                  <span>All</span>
                  <span className="pill-count">{compareJobsList.length}</span>
                </button>

                <button
                  type="button"
                  className={`status-filter-pill filter-running ${compareStatusFilter === "running" ? "active" : ""}`}
                  onClick={() => setCompareStatusFilter("running")}
                >
                  <span className="status-dot dot-running" />
                  <span>In Progress</span>
                  <span className="pill-count">{compareRunningCount}</span>
                </button>

                <button
                  type="button"
                  className={`status-filter-pill filter-queued ${compareStatusFilter === "queued" ? "active" : ""}`}
                  onClick={() => setCompareStatusFilter("queued")}
                >
                  <span className="status-dot dot-queued" />
                  <span>Pending</span>
                  <span className="pill-count">{compareQueuedCount}</span>
                </button>

                <button
                  type="button"
                  className={`status-filter-pill filter-completed ${compareStatusFilter === "completed" ? "active" : ""}`}
                  onClick={() => setCompareStatusFilter("completed")}
                >
                  <span className="status-dot dot-completed" />
                  <span>Completed</span>
                  <span className="pill-count">{compareCompletedCount}</span>
                </button>

                <button
                  type="button"
                  className={`status-filter-pill filter-failed ${compareStatusFilter === "failed" ? "active" : ""}`}
                  onClick={() => setCompareStatusFilter("failed")}
                >
                  <span className="status-dot dot-failed" />
                  <span>Failed</span>
                  <span className="pill-count">{compareFailedCount}</span>
                </button>
              </div>

              <div className="job-search-box">
                <input
                  type="text"
                  className="job-search-input"
                  placeholder="Search by Job ID or compared prompts..."
                  value={compareSearchQuery}
                  onChange={(e) => setCompareSearchQuery(e.target.value)}
                />
                {compareSearchQuery && (
                  <button className="btn-clear-search" onClick={() => setCompareSearchQuery("")}>
                    ✕
                  </button>
                )}
              </div>
            </div>

            {/* Table Content */}
            {filteredCompareJobs.length === 0 ? (
              <div className="jobs-empty-state">
                <div className="empty-icon">📭</div>
                <h4 className="empty-title">
                  {compareJobsList.length === 0 ? "No Benchmark Comparison Jobs Yet" : "No Jobs Match Selected Filter"}
                </h4>
                <p className="empty-subtitle">
                  {compareJobsList.length === 0
                    ? "Click 'Run Comparison Benchmark' above to execute a parallel comparison."
                    : "Try selecting 'All' or clearing your search query."}
                </p>
              </div>
            ) : (
              <div className="dev-table-container">
                <table className="dev-table jobs-queue-table">
                  <thead>
                    <tr>
                      <th>Job ID</th>
                      <th>Comparison Targets</th>
                      <th>Mode</th>
                      <th>Status</th>
                      <th>Progress</th>
                      <th>Output / Delta</th>
                      <th>Submitted At</th>
                      <th>Action</th>
                    </tr>
                  </thead>
                  <tbody>
                    {filteredCompareJobs.map((job) => {
                      const isRunning = job.status === "running";
                      const isQueued = job.status === "queued";
                      const isCompleted = job.status === "completed";
                      const isFailed = job.status === "failed" || job.status === "cancelled";
                      const pct =
                        job.progress_percent ??
                        Math.round(((job.progress_current || 0) / (job.progress_total || 1)) * 100);

                      const promptLabel = `${job.metadata?.prompt_a || "Prompt A"} vs ${job.metadata?.prompt_b || "Prompt B"}`;
                      const isDry = job.metadata?.dry_run !== false;

                      return (
                        <tr key={job.job_id} className={`job-row status-${job.status}`}>
                          {/* Job ID */}
                          <td className="table-id-cell">
                            <span
                              className="table-id-chip"
                              onClick={(e) => handleCopyJobId(e, job.job_id)}
                              title="Click to copy full Job ID"
                            >
                              <code>{job.job_id.slice(0, 8)}...</code>
                              <span className="copy-icon">
                                {copiedJobId === job.job_id ? "✓" : "📋"}
                              </span>
                            </span>
                          </td>

                          {/* Target Prompts */}
                          <td className="table-target-cell">
                            <code className="target-prompt-code">{promptLabel}</code>
                          </td>

                          {/* Mode */}
                          <td>
                            <span className={`job-mode-pill ${isDry ? "mode-dry" : "mode-live"}`}>
                              {isDry ? "⚡ Dry-Run" : "✨ Live"}
                            </span>
                          </td>

                          {/* Status */}
                          <td>
                            <span className={`status-badge-chip badge-${job.status}`}>
                              {isRunning && <span className="status-spinner-small" />}
                              {isQueued && "⏳ "}
                              {isCompleted && "✓ "}
                              {isFailed && "❌ "}
                              {job.status.toUpperCase()}
                            </span>
                          </td>

                          {/* Progress */}
                          <td className="table-progress-cell">
                            {isCompleted ? (
                              <span className="text-green-pct">100% ({job.progress_total || "All"} Cases)</span>
                            ) : (
                              <div className="table-mini-progress">
                                <div className="table-mini-bar-wrap">
                                  <div
                                    className={`table-mini-bar-fill ${isRunning ? "active" : ""}`}
                                    style={{ width: `${Math.max(5, Math.min(100, pct))}%` }}
                                  />
                                </div>
                                <span className="table-mini-progress-label">
                                  {pct}% ({job.progress_current || 0}/{job.progress_total || 1})
                                </span>
                              </div>
                            )}
                          </td>

                          {/* Metrics / Output */}
                          <td className="table-metrics-cell">
                            {isCompleted && job.metadata?.accuracy_delta !== undefined ? (
                              <span className={`metric-tag ${job.metadata.accuracy_delta >= 0 ? "accuracy-tag" : "error-tag"}`}>
                                Acc Δ: <strong>{job.metadata.accuracy_delta >= 0 ? `+${(job.metadata.accuracy_delta * 100).toFixed(1)}%` : `${(job.metadata.accuracy_delta * 100).toFixed(1)}%`}</strong>
                              </span>
                            ) : isCompleted ? (
                              <span className="metric-tag completed-tag">Comparison Ready</span>
                            ) : isFailed ? (
                              <span className="metric-tag error-tag" title={job.error_message || "Failed"}>
                                ⚠️ {job.error_message ? job.error_message.slice(0, 30) + "..." : "Error"}
                              </span>
                            ) : (
                              <span className="metric-tag queued-tag">
                                {isRunning ? "Comparing dual prompts..." : "Queued"}
                              </span>
                            )}
                          </td>

                          {/* Submitted At */}
                          <td className="time-cell" title={job.created_at || ""}>
                            {formatTime(job.created_at)}
                          </td>

                          {/* Actions */}
                          <td className="table-action-cell">
                            {isCompleted ? (
                              <button
                                type="button"
                                className="btn-inspect"
                                onClick={() => handleInspectJob(job)}
                                disabled={inspectingJobId === job.job_id}
                              >
                                {inspectingJobId === job.job_id ? "Loading..." : "Inspect ↗"}
                              </button>
                            ) : isRunning ? (
                              <span className="running-live-tag">
                                <span className="status-spinner-small" /> Live
                              </span>
                            ) : (
                              <span className="table-idle-text">—</span>
                            )}
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </div>

          {/* Side-by-Side Comparison Results Visualizer */}
          {comparisonData && (
            <div className="results-visualizer">
              <div className="results-top-banner compare-banner">
                <div className="results-title-group">
                  <span className="results-badge">Benchmark Comparison Complete</span>
                  <h4 className="results-heading">
                    <code>{comparisonData.prompt_a}</code> vs <code>{comparisonData.prompt_b}</code>
                  </h4>
                </div>
                <span className="total-badge">{comparisonData.prediction_diffs?.length || 25} Test Cases Evaluated</span>
              </div>

              {/* KPI Delta Grid */}
              <div className="compare-kpi-grid">
                {comparisonData.metrics?.map((m, idx) => (
                  <div key={idx} className="compare-kpi-cell">
                    <span className="cell-metric-name">{m.name}</span>
                    <div className="cell-values">
                      <span className="val-a">{m.is_pct ? formatPct(m.val_a) : m.val_a.toFixed(2)}</span>
                      <span className="val-arrow">➜</span>
                      <span className="val-b">{m.is_pct ? formatPct(m.val_b) : m.val_b.toFixed(2)}</span>
                    </div>
                    <span className={`cell-delta ${m.status === "improved" ? "text-green" : m.status === "regressed" ? "text-red" : ""}`}>
                      {m.delta_str}
                    </span>
                  </div>
                ))}
              </div>

              {/* Per-Tier Comparison Table */}
              <div className="dev-card">
                <h4 className="card-heading">Per-Tier F1 Score Comparison Matrix</h4>
                <div className="dev-table-container">
                  <table className="dev-table">
                    <thead>
                      <tr>
                        <th>Tier</th>
                        <th>{comparisonData.prompt_a} F1</th>
                        <th>{comparisonData.prompt_b} F1</th>
                        <th>F1 Delta</th>
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
      {/* VIEW 3: PROMPT REGISTRY & MANAGEMENT                               */}
      {/* =================================================================== */}
      {activeTab === "prompt-management" && (
        <div className="dev-page-section">
          {promptActionMsg && (
            <div className={`dev-alert-${promptActionMsg.type === "error" ? "danger" : "success"}`}>
              <span>{promptActionMsg.type === "error" ? "⚠️" : "✓"}</span>
              <span>{promptActionMsg.text}</span>
            </div>
          )}

          {/* Prompt Creator Panel */}
          {showCreatePrompt && (
            <div className="prompt-create-card">
              <div className="preview-drawer-header">
                <div className="preview-title-group">
                  <span className="prompt-badge badge-custom">New Revision</span>
                  <h4 className="preview-title">Register New Scoring Prompt Template</h4>
                </div>
                <button
                  type="button"
                  className="btn-close-preview"
                  onClick={() => setShowCreatePrompt(false)}
                >
                  ✕
                </button>
              </div>

              <form onSubmit={handleRegisterPrompt}>
                <div className="prompt-form-row">
                  <div className="prompt-form-field">
                    <label>Prompt Name</label>
                    <input
                      type="text"
                      value={newPromptName}
                      onChange={(e) => setNewPromptName(e.target.value)}
                      placeholder="account_scoring"
                      required
                    />
                  </div>
                  <div className="prompt-form-field">
                    <label>Version Tag</label>
                    <input
                      type="text"
                      value={newPromptVersion}
                      onChange={(e) => setNewPromptVersion(e.target.value)}
                      placeholder="v2.1-risk-focus"
                      required
                    />
                  </div>
                  <div className="prompt-form-field">
                    <label>Prompt Type</label>
                    <select
                      value={newPromptType}
                      onChange={(e) => setNewPromptType(e.target.value)}
                    >
                      <option value="scoring">Scoring &amp; Triage</option>
                      <option value="reasoning">Chain-of-Thought Reasoning</option>
                      <option value="classifier">Risk Classifier</option>
                    </select>
                  </div>
                </div>

                <div className="prompt-form-field" style={{ marginTop: "14px" }}>
                  <label>
                    System Prompt Instructions (must contain <code>{`{account_context}`}</code>)
                  </label>
                  <textarea
                    className="prompt-template-textarea"
                    rows={12}
                    value={newPromptTemplate}
                    onChange={(e) => setNewPromptTemplate(e.target.value)}
                    placeholder="Enter prompt instructions for Gemini LLM..."
                    required
                  />
                </div>

                <div className="prompt-create-actions" style={{ marginTop: "14px" }}>
                  <button
                    type="button"
                    className="btn-cancel-create"
                    onClick={() => {
                      // Insert starter from v2.0
                      const v2 = prompts.find((p) => p.version === "v2.0");
                      if (v2) {
                        setNewPromptTemplate(v2.template);
                        setNewPromptVersion("v2.1-custom");
                      }
                    }}
                  >
                    📋 Pre-fill from v2.0 Production
                  </button>
                  <button
                    type="button"
                    className="btn-cancel-create"
                    onClick={() => setShowCreatePrompt(false)}
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    className="btn-save-prompt"
                    disabled={promptActionLoading}
                  >
                    {promptActionLoading ? <span className="page-spinner" /> : "✓"}
                    <span>Register Prompt</span>
                  </button>
                </div>
              </form>
            </div>
          )}

          {/* Prompts Management Toolbar & Table */}
          <div className="dev-card prompt-mgmt-card">
            <div className="jobs-queue-header">
              <div className="jobs-header-left">
                <h3 className="section-title">System Prompt Registry ({prompts.length} Versions)</h3>
                <p className="jobs-header-desc">
                  Browse prompt versions, preview system instructions, compare textual diffs, delete custom revisions, or launch benchmark evaluations.
                </p>
              </div>

              <div className="jobs-header-actions">
                <button
                  type="button"
                  className="btn-new-prompt"
                  onClick={() => {
                    setShowCreatePrompt(true);
                    setPromptActionMsg(null);
                  }}
                >
                  <span>+</span>
                  <span>Register New Prompt</span>
                </button>

                <button
                  type="button"
                  className={`btn-compare-prompts-toggle ${showDiffViewer ? "active" : ""}`}
                  onClick={() => setShowDiffViewer(!showDiffViewer)}
                >
                  <span>⚖️</span>
                  <span>{showDiffViewer ? "Hide Diff" : "Compare Prompts Diff"}</span>
                </button>

                <button
                  type="button"
                  className="btn-refresh-manual"
                  onClick={loadPrompts}
                  disabled={loadingPrompts}
                >
                  {loadingPrompts ? <span className="page-spinner" /> : "🔄"}
                  <span>Sync Prompts</span>
                </button>
              </div>
            </div>

            {/* Prompt Search Input */}
            <div className="prompt-mgmt-toolbar">
              <div className="prompt-search-wrap">
                <input
                  type="text"
                  className="prompt-search-input"
                  placeholder="Search prompts by version, name, or keywords..."
                  value={promptSearchFilter}
                  onChange={(e) => setPromptSearchFilter(e.target.value)}
                />
                {promptSearchFilter && (
                  <button className="btn-clear-search" onClick={() => setPromptSearchFilter("")}>
                    ✕
                  </button>
                )}
              </div>

              <span className="pagination-info">
                Showing {filteredPrompts.length} of {prompts.length} registered versions
              </span>
            </div>

            {/* Prompts Table */}
            <div className="dev-table-container">
              <table className="dev-table jobs-queue-table">
                <thead>
                  <tr>
                    <th>Version</th>
                    <th>Name</th>
                    <th>Type</th>
                    <th>Template Stats</th>
                    <th>Status</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredPrompts.map((p) => {
                    const isProd = p.version === "v2.0";
                    const isBaseline = p.version === "v1.0";
                    const lineCount = p.template ? p.template.split("\n").length : 0;
                    const charCount = p.template ? p.template.length : 0;

                    return (
                      <tr key={p.version}>
                        {/* Version */}
                        <td>
                          <code className="target-prompt-code" style={{ fontWeight: 700 }}>
                            {p.version}
                          </code>
                        </td>

                        {/* Name */}
                        <td>
                          <span style={{ fontWeight: 600, color: "var(--text-primary)" }}>
                            {p.name}
                          </span>
                        </td>

                        {/* Type */}
                        <td>
                          <span className="job-mode-pill mode-dry">
                            {p.type || "scoring"}
                          </span>
                        </td>

                        {/* Template Stats */}
                        <td>
                          <span className="preview-stat-chip">
                            {lineCount} lines · {charCount.toLocaleString()} chars
                          </span>
                        </td>

                        {/* Status Tag */}
                        <td>
                          {isProd ? (
                            <span className="prompt-badge badge-prod">Production Default</span>
                          ) : isBaseline ? (
                            <span className="prompt-badge badge-baseline">Baseline Initial</span>
                          ) : (
                            <span className="prompt-badge badge-custom">Custom Revision</span>
                          )}
                        </td>

                        {/* Actions */}
                        <td>
                          <div className="prompt-actions-cell">
                            <button
                              type="button"
                              className="btn-prompt-preview"
                              onClick={() => {
                                setPreviewPrompt(p);
                                setTimeout(() => {
                                  document.querySelector(".prompt-preview-drawer")?.scrollIntoView({ behavior: "smooth" });
                                }, 50);
                              }}
                              title="Preview prompt template"
                            >
                              👁️ Preview
                            </button>

                            <button
                              type="button"
                              className="btn-prompt-diff"
                              onClick={() => {
                                setDiffPromptA("v1.0");
                                setDiffPromptB(p.version);
                                setShowDiffViewer(true);
                                setTimeout(() => {
                                  document.querySelector(".prompt-diff-card")?.scrollIntoView({ behavior: "smooth" });
                                }, 50);
                              }}
                              title="Compare diff against v1.0"
                            >
                              ⚖️ Diff
                            </button>

                            <button
                              type="button"
                              className="btn-prompt-eval"
                              onClick={() => {
                                setSelectedPrompt(p.version);
                                setIsCustomPrompt(false);
                                setActiveTab("single-run");
                              }}
                              title="Run evaluation with this prompt"
                            >
                              🚀 Test Eval
                            </button>

                            <button
                              type="button"
                              className="btn-prompt-delete"
                              onClick={() => handleDeletePrompt(p)}
                              disabled={isProd || isBaseline}
                              title={isProd || isBaseline ? "Canonical prompt cannot be deleted" : "Delete custom prompt"}
                            >
                              🗑️
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Interactive Side-by-Side Prompt Diff Viewer */}
          {showDiffViewer && (
            <div className="prompt-diff-card">
              <div className="preview-drawer-header">
                <div className="preview-title-group">
                  <span className="prompt-badge badge-baseline">Visual Diff</span>
                  <h4 className="preview-title">
                    Side-by-Side Prompt Diff: <code>{diffPromptA}</code> vs <code>{diffPromptB}</code>
                  </h4>
                </div>
                <div className="preview-header-actions">
                  <button
                    type="button"
                    className="btn-prompt-eval"
                    onClick={() => {
                      setComparePromptA(diffPromptA);
                      setComparePromptB(diffPromptB);
                      setActiveTab("benchmark-compare");
                    }}
                  >
                    ⚖️ Launch Benchmark Comparison (A vs B) ➜
                  </button>
                  <button
                    type="button"
                    className="btn-close-preview"
                    onClick={() => setShowDiffViewer(false)}
                  >
                    ✕
                  </button>
                </div>
              </div>

              {/* Diff Selectors */}
              <div className="diff-selectors-row">
                <div className="diff-prompt-select-group">
                  <span className="diff-select-label">Prompt A (Baseline):</span>
                  <select
                    className="diff-select"
                    value={diffPromptA}
                    onChange={(e) => setDiffPromptA(e.target.value)}
                  >
                    {prompts.map((p) => (
                      <option key={p.version} value={p.version}>
                        {p.version} ({p.name})
                      </option>
                    ))}
                  </select>
                </div>

                <div className="vs-divider" style={{ width: "40px", margin: "0" }}>
                  <span>VS</span>
                </div>

                <div className="diff-prompt-select-group">
                  <span className="diff-select-label">Prompt B (Candidate):</span>
                  <select
                    className="diff-select"
                    value={diffPromptB}
                    onChange={(e) => setDiffPromptB(e.target.value)}
                  >
                    {prompts.map((p) => (
                      <option key={p.version} value={p.version}>
                        {p.version} ({p.name})
                      </option>
                    ))}
                  </select>
                </div>

                <span style={{ fontSize: "0.78rem", color: "var(--text-muted)", marginLeft: "auto" }}>
                  {diffRows.filter((r) => r.status !== "same").length} lines modified
                </span>
              </div>

              {/* Side-by-Side Lines */}
              <div className="diff-side-by-side-container">
                <div className="diff-column">
                  <div className="diff-col-header">Prompt A: {diffPromptA}</div>
                  <div className="diff-col-content">
                    {diffRows.map((r, idx) => (
                      <div
                        key={idx}
                        className={`diff-line ${
                          r.status === "removed" ? "diff-removed" : r.status === "changed" ? "diff-changed" : ""
                        }`}
                      >
                        <span className="diff-line-num">{r.lineNum}</span>
                        <span className="diff-line-text">{r.lineA !== null ? r.lineA : " "}</span>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="diff-column">
                  <div className="diff-col-header">Prompt B: {diffPromptB}</div>
                  <div className="diff-col-content">
                    {diffRows.map((r, idx) => (
                      <div
                        key={idx}
                        className={`diff-line ${
                          r.status === "added" ? "diff-added" : r.status === "changed" ? "diff-changed" : ""
                        }`}
                      >
                        <span className="diff-line-num">{r.lineNum}</span>
                        <span className="diff-line-text">{r.lineB !== null ? r.lineB : " "}</span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Interactive Prompt Template Preview Drawer */}
          {previewPrompt && (
            <div className="prompt-preview-drawer">
              <div className="preview-drawer-header">
                <div className="preview-title-group">
                  <span className={`prompt-badge ${previewPrompt.version === "v2.0" ? "badge-prod" : previewPrompt.version === "v1.0" ? "badge-baseline" : "badge-custom"}`}>
                    {previewPrompt.version}
                  </span>
                  <h4 className="preview-title">{previewPrompt.name} Template Preview</h4>
                  <div className="preview-stats-chips">
                    <span className="preview-stat-chip">
                      {previewPrompt.template.split("\n").length} Lines
                    </span>
                    <span className="preview-stat-chip">
                      {previewPrompt.template.length.toLocaleString()} Characters
                    </span>
                    <span className="preview-stat-chip">
                      Type: {previewPrompt.type || "scoring"}
                    </span>
                  </div>
                </div>

                <div className="preview-header-actions">
                  <button
                    type="button"
                    className="btn-copy-template"
                    onClick={() => handleCopyTemplate(previewPrompt.template)}
                  >
                    {copiedTemplate ? "✓ Copied" : "📋 Copy Template"}
                  </button>

                  <button
                    type="button"
                    className="btn-prompt-eval"
                    onClick={() => {
                      setSelectedPrompt(previewPrompt.version);
                      setIsCustomPrompt(false);
                      setActiveTab("single-run");
                    }}
                  >
                    🚀 Run Single Eval With This Prompt ➜
                  </button>

                  <button
                    type="button"
                    className="btn-close-preview"
                    onClick={() => setPreviewPrompt(null)}
                  >
                    ✕
                  </button>
                </div>
              </div>

              <div className="prompt-code-view-container">
                <pre className="prompt-code-pre">{previewPrompt.template}</pre>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
};

export default DeveloperEvalPage;

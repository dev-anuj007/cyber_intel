import axios, { AxiosInstance } from "axios";
import {
  Account,
  AccountVersionSummary,
  AccountScore,
  SummaryStats,
  LLMStats,
  UserProfile,
  AuthResponse,
  BackgroundJobDetail,
  BackgroundJobListResponse,
  JobSubmitResponse,
  ScannerEngineInfo,
  PromptTemplateInfo,
  PromptRegisterRequest,
} from "./types";

const API_BASE_URL = import.meta.env.VITE_API_URL || "http://localhost:8000/api";

class APIClient {
  private client: AxiosInstance;

  constructor(baseURL: string = API_BASE_URL) {
    this.client = axios.create({
      baseURL,
      headers: {
        "Content-Type": "application/json",
      },
    });

    // Automatically inject JWT bearer token if present
    this.client.interceptors.request.use((config) => {
      const token = localStorage.getItem("token");
      if (token && config.headers) {
        config.headers.Authorization = `Bearer ${token}`;
      }
      return config;
    });

    // Normalize error boundary responses
    this.client.interceptors.response.use(
      (response) => response,
      (error) => {
        const errorData = error.response?.data;
        if (errorData) {
          const extractedMsg =
            errorData.error?.message ||
            errorData.detail ||
            (errorData.error?.details && Array.isArray(errorData.error.details)
              ? errorData.error.details.map((d: any) => `${d.field}: ${d.message}`).join(", ")
              : null) ||
            error.message ||
            "An unexpected error occurred";

          error.userMessage = extractedMsg;
          error.errorCode = errorData.error?.code;
          error.traceId = errorData.error?.trace_id || error.response?.headers?.["x-trace-id"];
        }
        return Promise.reject(error);
      }
    );
  }


  // Auth Methods
  async signup(email: string, password: string): Promise<AuthResponse> {
    const response = await this.client.post<AuthResponse>("/auth/signup", {
      email,
      password,
    });
    return response.data;
  }

  async signin(email: string, password: string): Promise<AuthResponse> {
    const response = await this.client.post<AuthResponse>("/auth/signin", {
      email,
      password,
    });
    return response.data;
  }

  async getCurrentUser(): Promise<UserProfile> {
    const response = await this.client.get<UserProfile>("/auth/me");
    return response.data;
  }

  async updateApiKey(apiKey: string): Promise<UserProfile> {
    const response = await this.client.post<UserProfile>("/auth/api-key", {
      api_key: apiKey,
    });
    return response.data;
  }

  async deleteApiKey(): Promise<UserProfile> {
    const response = await this.client.delete<UserProfile>("/auth/api-key");
    return response.data;
  }

  // Platform & Accounts
  async getSummary(): Promise<SummaryStats> {
    const response = await this.client.get<SummaryStats>("/summary");
    return response.data;
  }

  async listAccounts(skip: number = 0, limit: number = 20, filters?: any) {
    const response = await this.client.get("/accounts", {
      params: { skip, limit, ...filters },
    });
    return response.data;
  }

  async getAccount(accountKey: string, version?: string): Promise<Account> {
    const params = version ? { version } : {};
    const response = await this.client.get<Account>(`/accounts/${encodeURIComponent(accountKey)}`, { params });
    return response.data;
  }

  async getAccountVersions(accountKey: string): Promise<AccountVersionSummary[]> {
    const response = await this.client.get<{ account_key: string; total_versions: number; versions: AccountVersionSummary[] }>(
      `/accounts/${encodeURIComponent(accountKey)}/versions`
    );
    return response.data?.versions || [];
  }

  async scoreAccount(accountOrKey: Account | string): Promise<AccountScore> {
    const accountKey = typeof accountOrKey === "string" ? accountOrKey : accountOrKey.account_key;
    const response = await this.client.post<AccountScore>("/score", {
      account_key: accountKey,
    });
    return response.data;
  }

  async scoreBatch(accountKeys: string[], limit: number = 10): Promise<AccountScore[]> {
    const response = await this.client.post<AccountScore[]>("/score/batch", {
      account_keys: accountKeys,
      limit,
    });
    return response.data;
  }

  async getLLMStats(): Promise<LLMStats> {
    const response = await this.client.get<LLMStats>("/llm-stats");
    return response.data;
  }

  async getScoreHistory(accountKey: string, version?: string): Promise<any> {
    const params = version ? { version } : {};
    const response = await this.client.get(`/accounts/${encodeURIComponent(accountKey)}/score-history`, { params });
    return response.data;
  }

  async searchAccounts(query: string) {
    const response = await this.client.get("/search", {
      params: { q: query },
    });
    return response.data;
  }

  async getAccountsBySignal(signalName: string, skip: number = 0, limit: number = 20) {
    const response = await this.client.get(`/accounts/by-signal/${signalName}`, {
      params: { skip, limit },
    });
    return response.data;
  }

  // Developer & Eval Harness Methods
  async getEvalPrompts(): Promise<{ prompts: PromptTemplateInfo[] }> {
    const response = await this.client.get("/eval/prompts");
    return response.data;
  }

  async listPrompts(): Promise<{ prompts: PromptTemplateInfo[] }> {
    const response = await this.client.get("/prompts");
    return response.data;
  }

  async getPrompt(name: string, version: string): Promise<PromptTemplateInfo> {
    const response = await this.client.get(`/prompts/${encodeURIComponent(name)}/${encodeURIComponent(version)}`);
    return response.data;
  }

  async registerPrompt(data: PromptRegisterRequest): Promise<PromptTemplateInfo> {
    const response = await this.client.post("/prompts", data);
    return response.data;
  }

  async deletePrompt(name: string, version: string): Promise<{ success: boolean; message: string }> {
    const response = await this.client.delete(`/prompts/${encodeURIComponent(name)}/${encodeURIComponent(version)}`);
    return response.data;
  }

  async getEvalDataset(): Promise<{ dataset: any[]; total: number }> {
    const response = await this.client.get("/eval/dataset");
    return response.data;
  }

  async runEval(params: {
    prompt_version?: string;
    custom_prompt_template?: string;
    dry_run?: boolean;
    eval_set_path?: string;
    eval_set?: any[];
    sample_limit?: number;
  }): Promise<any> {
    const response = await this.client.post("/eval/run", params);
    return response.data;
  }

  async compareEval(params: {
    prompt_a?: string;
    prompt_b?: string;
    custom_prompt_a?: string;
    custom_prompt_b?: string;
    dry_run?: boolean;
    file_a?: string;
    file_b?: string;
    eval_set_path?: string;
    eval_set?: any[];
    sample_limit?: number;
  }): Promise<any> {
    const response = await this.client.post("/eval/compare", params);
    return response.data;
  }

  async getEvalHistory(): Promise<{ history: any[] }> {
    const response = await this.client.get("/eval/history");
    return response.data;
  }

  async getEvalResultFile(filename: string): Promise<any> {
    const response = await this.client.get(`/eval/results/${encodeURIComponent(filename)}`);
    return response.data;
  }

  // Web Crawler & Prospecting Methods (App)
  async getAvailableScanners(): Promise<{ scanners: ScannerEngineInfo[] }> {
    const response = await this.client.get<{ scanners: ScannerEngineInfo[] }>("/crawler/scanners");
    return response.data;
  }

  async runCrawler(params: {
    domains: string[];
    scan_depth?: string;
    scanner_type?: string;
    enable_subdomains?: boolean;
    custom_ports?: number[];
    save_to_database?: boolean;
  }): Promise<any> {
    const response = await this.client.post("/crawler/run", params);
    return response.data;
  }

  async submitCrawlerJob(params: {
    domains: string[];
    pipeline_name?: string;
    scan_depth?: string;
    scanner_type?: string;
    enable_subdomains?: boolean;
    custom_ports?: number[];
    save_to_database?: boolean;
  }): Promise<JobSubmitResponse> {
    const response = await this.client.post("/crawler/jobs", params);
    return response.data;
  }

  async listCrawlerJobs(params?: {
    skip?: number;
    limit?: number;
    status?: string;
  }): Promise<BackgroundJobListResponse> {
    const response = await this.client.get("/crawler/jobs", { params });
    return response.data;
  }

  async getCrawlerJob(jobId: string): Promise<BackgroundJobDetail> {
    const response = await this.client.get(`/crawler/jobs/${jobId}`);
    return response.data;
  }

  async retryCrawlerJob(jobId: string): Promise<JobSubmitResponse> {
    const response = await this.client.post(`/crawler/jobs/${jobId}/retry`);
    return response.data;
  }

  async listJobs(params?: {
    skip?: number;
    limit?: number;
    job_type?: string;
    status?: string;
  }): Promise<BackgroundJobListResponse> {
    const response = await this.client.get("/jobs", { params });
    return response.data;
  }

  async getJob(jobId: string): Promise<BackgroundJobDetail> {
    const response = await this.client.get(`/jobs/${jobId}`);
    return response.data;
  }
}

export const api = new APIClient();



SQLITE_SCHEMA_STATEMENTS = [
    """
    CREATE TABLE IF NOT EXISTS accounts (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_key TEXT UNIQUE NOT NULL,
        signal_count INTEGER DEFAULT 0,
        priority_tier TEXT DEFAULT 'tier_4_low',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS domains (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id INTEGER NOT NULL,
        domain TEXT NOT NULL,
        FOREIGN KEY(account_id) REFERENCES accounts(id),
        UNIQUE(account_id, domain)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS assets (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id INTEGER NOT NULL,
        ip TEXT,
        port INTEGER,
        hostname TEXT,
        FOREIGN KEY(account_id) REFERENCES accounts(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ips (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id INTEGER NOT NULL,
        ip TEXT NOT NULL,
        FOREIGN KEY(account_id) REFERENCES accounts(id),
        UNIQUE(account_id, ip)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS hostnames (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id INTEGER NOT NULL,
        hostname TEXT NOT NULL,
        FOREIGN KEY(account_id) REFERENCES accounts(id),
        UNIQUE(account_id, hostname)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ports (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id INTEGER NOT NULL,
        port INTEGER NOT NULL,
        FOREIGN KEY(account_id) REFERENCES accounts(id),
        UNIQUE(account_id, port)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id INTEGER NOT NULL,
        product TEXT NOT NULL,
        FOREIGN KEY(account_id) REFERENCES accounts(id),
        UNIQUE(account_id, product)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS cloud_providers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id INTEGER NOT NULL,
        provider TEXT NOT NULL,
        FOREIGN KEY(account_id) REFERENCES accounts(id),
        UNIQUE(account_id, provider)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS signals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        severity TEXT NOT NULL,
        category TEXT NOT NULL,
        evidence TEXT NOT NULL,
        FOREIGN KEY(account_id) REFERENCES accounts(id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ai_scores (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        account_key TEXT NOT NULL,
        version INTEGER NOT NULL DEFAULT 1,
        score INTEGER NOT NULL,
        priority_tier TEXT NOT NULL,
        key_risks TEXT NOT NULL,
        suggested_outreach TEXT NOT NULL,
        score_rationale TEXT DEFAULT '',
        model_version TEXT NOT NULL,
        model_name TEXT DEFAULT 'gemini-3.1-flash-lite',
        tokens_used TEXT,
        latency_ms INTEGER DEFAULT 0,
        cost_usd REAL DEFAULT 0.0,
        scored_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_latest INTEGER DEFAULT 1
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        salt TEXT NOT NULL,
        full_name TEXT,
        role TEXT DEFAULT 'member',
        gemini_api_key TEXT,
        api_key TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS background_jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id TEXT UNIQUE NOT NULL,
        job_type TEXT NOT NULL,
        title TEXT NOT NULL,
        user_id INTEGER,
        status TEXT NOT NULL DEFAULT 'queued',
        progress_current INTEGER NOT NULL DEFAULT 0,
        progress_total INTEGER NOT NULL DEFAULT 0,
        retry_count INTEGER NOT NULL DEFAULT 0,
        max_retries INTEGER NOT NULL DEFAULT 3,
        payload_json TEXT NOT NULL,
        results_json TEXT,
        metadata_json TEXT,
        error_message TEXT,
        trace_id TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        started_at TIMESTAMP,
        completed_at TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS crawler_jobs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        job_id TEXT UNIQUE NOT NULL,
        user_id INTEGER,
        status TEXT NOT NULL DEFAULT 'queued',
        scan_depth TEXT NOT NULL DEFAULT 'standard',
        enable_subdomains INTEGER DEFAULT 1,
        custom_ports TEXT,
        save_to_database INTEGER DEFAULT 1,
        domains_input TEXT NOT NULL,
        domains_count INTEGER DEFAULT 0,
        completed_count INTEGER DEFAULT 0,
        assets_discovered_count INTEGER DEFAULT 0,
        signals_detected_count INTEGER DEFAULT 0,
        retry_count INTEGER DEFAULT 0,
        max_retries INTEGER DEFAULT 3,
        results_json TEXT,
        error_message TEXT,
        trace_id TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        started_at TIMESTAMP,
        completed_at TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS eval_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        run_id TEXT UNIQUE NOT NULL,
        prompt_version TEXT NOT NULL,
        total_samples INTEGER NOT NULL,
        tier_accuracy REAL NOT NULL,
        macro_f1 REAL NOT NULL,
        weighted_f1 REAL NOT NULL,
        critical_threat_recall REAL NOT NULL,
        score_tier_consistency REAL NOT NULL,
        score_mae REAL NOT NULL,
        score_rmse REAL NOT NULL,
        within_5_points INTEGER NOT NULL,
        within_5_points_pct REAL NOT NULL,
        tier_metrics_json TEXT NOT NULL,
        predictions_json TEXT NOT NULL,
        results_json TEXT NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
]

SQLITE_INDEX_STATEMENTS = [
    "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)",
    "CREATE INDEX IF NOT EXISTS idx_account_key ON accounts(account_key)",
    "CREATE INDEX IF NOT EXISTS idx_accounts_signal_count ON accounts(signal_count DESC)",
    "CREATE INDEX IF NOT EXISTS idx_accounts_tier_signal_count ON accounts(priority_tier, signal_count DESC)",
    "CREATE INDEX IF NOT EXISTS idx_domain ON domains(domain)",
    "CREATE INDEX IF NOT EXISTS idx_domains_account_id ON domains(account_id)",
    "CREATE INDEX IF NOT EXISTS idx_assets_account_id ON assets(account_id)",
    "CREATE INDEX IF NOT EXISTS idx_ips_account_id ON ips(account_id)",
    "CREATE INDEX IF NOT EXISTS idx_ips_ip ON ips(ip)",
    "CREATE INDEX IF NOT EXISTS idx_hostnames_account_id ON hostnames(account_id)",
    "CREATE INDEX IF NOT EXISTS idx_ports_account_id ON ports(account_id)",
    "CREATE INDEX IF NOT EXISTS idx_products_account_id ON products(account_id)",
    "CREATE INDEX IF NOT EXISTS idx_cloud_providers_account_id ON cloud_providers(account_id)",
    "CREATE INDEX IF NOT EXISTS idx_signals_account_id ON signals(account_id)",
    "CREATE INDEX IF NOT EXISTS idx_signal_severity ON signals(severity)",
    "CREATE INDEX IF NOT EXISTS idx_signal_name ON signals(name)",
    "CREATE INDEX IF NOT EXISTS idx_signals_acc_sev ON signals(account_id, severity)",
    "CREATE INDEX IF NOT EXISTS idx_signals_sev_acc ON signals(severity, account_id)",
    "CREATE INDEX IF NOT EXISTS idx_signals_name_acc ON signals(name, account_id)",
    "CREATE INDEX IF NOT EXISTS idx_assets_cov ON assets(account_id, ip, port, hostname)",
    "CREATE INDEX IF NOT EXISTS idx_signals_cov ON signals(account_id, name, severity, category, evidence)",
    "CREATE INDEX IF NOT EXISTS idx_ai_scores_acc_key ON ai_scores(account_key)",
    "CREATE INDEX IF NOT EXISTS idx_ai_scores_latest ON ai_scores(account_key, is_latest)",
    "CREATE INDEX IF NOT EXISTS idx_ai_scores_scored_at ON ai_scores(scored_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_bg_jobs_id ON background_jobs(job_id)",
    "CREATE INDEX IF NOT EXISTS idx_bg_jobs_type_status ON background_jobs(job_type, status)",
    "CREATE INDEX IF NOT EXISTS idx_bg_jobs_created_at ON background_jobs(created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_eval_runs_id ON eval_runs(run_id)",
    "CREATE INDEX IF NOT EXISTS idx_eval_runs_prompt_ver ON eval_runs(prompt_version)",
    "CREATE INDEX IF NOT EXISTS idx_eval_runs_created_at ON eval_runs(created_at DESC)",
]

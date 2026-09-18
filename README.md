# Cybersecurity Sales Intelligence Platform

An AI-native B2B sales prospecting and attack surface intelligence platform that identifies, scores, and prioritizes businesses most likely to need cybersecurity solutions right now.

---

## ⚡ Quick Start

### Prerequisites
- Python 3.10+
- Node.js 18+
- Google Gemini API Key (`GEMINI_API_KEY`)

### 1. Backend Setup

```bash
cd backend
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt

# Start FastAPI server on port 8000
python src/main.py
```

### 2. Frontend Setup

```bash
cd frontend
npm install
npm run dev
```
Open `http://localhost:5173` in your browser.

---

## 📁 Repository Structure

```
.
├── backend/                 # FastAPI backend & database engine
│   ├── src/
│   │   ├── main.py          # FastAPI REST routes (search, filters, scoring)
│   │   ├── models.py        # Pydantic data contracts (Account, Signal, LLMTrace)
│   │   ├── database.py      # SQLite query engine (50,000+ accounts)
│   │   └── account_scorer.py# LLM scoring & tracing engine (Google GenAI)
│   ├── traces/              # Immutable JSONL LLM execution logs
│   └── requirements.txt
│
├── frontend/                # React 18 + TypeScript SPA
│   ├── src/
│   │   ├── App.tsx          # Main dashboard view & layout
│   │   ├── components/      # UI components (AccountList, Detail, Header, Search)
│   │   ├── store.ts         # Zustand state management
│   │   └── api.ts           # Axios backend client
│   └── package.json
│
├── skills/                  # Reusable Agent Skills (SKILL.md specs)
│   ├── account-scoring/
│   │   └── SKILL.md         # Account risk scoring & prioritization skill
│   └── outreach-generator/
│       └── SKILL.md         # Consultative sales outreach generator skill
│
├── prompts/                 # Versioned Prompt Registry
│   ├── account_scoring_v1.0.txt  # Baseline prompt
│   ├── account_scoring_v2.0.txt  # Calibrated production prompt with strict tiers
│   └── outreach_draft_v1.0.txt   # Consultative outreach generation prompt
│
├── backend/src/services/eval/ # Self-Contained Evaluation Microservice
│   ├── labeled_sets/
│   │   └── eval_v1.json     # 25 hand-labeled ground-truth benchmark cases
│   ├── results/             # Versioned evaluation benchmark reports
│   ├── eval_harness.py      # One-command eval & comparative benchmark runner
│   ├── eval_service.py      # Eval service orchestration & repository layer
│   └── api.py               # REST API endpoints (/api/eval/*)
│
└── docs/                    # Technical & Strategic Documentation
    ├── PLANNING.md          # Strategy, ICP, buyer personas & workflows
    ├── ARCHITECTURE.md      # System architecture, rule-vs-LLM split, cost model
    └── HOW_YOU_BUILD.md     # Agentic dev loop reflection & trade-offs
```

---

## 🔬 AI-Native Scaffolding & Evaluation

### Run Evaluation Harness
Run the evaluation harness on the calibrated **Prompt v2.0**:
```bash
python -m src.services.eval.eval_harness --prompt-version v2.0
```

### Run Side-by-Side Prompt Comparison (v1.0 vs v2.0)
```bash
python -m src.services.eval.eval_harness --compare
```
This runs both prompt versions against the 25 hand-labeled ground-truth test cases and outputs a side-by-side performance table measuring:
- **Tier Classification Accuracy**
- **Precision, Recall, and F1-Scores** per tier
- **Macro and Weighted F1-Scores**
- **Score MAE (Mean Absolute Error) & RMSE**
- **% of predictions within ±5 points**

---

## 💰 Production Cost Economics

| Model | Task | Cost per Account | Cost per 1,000 Accounts |
| :--- | :--- | :--- | :--- |
| **Gemini 3.6 Flash / Flash Lite** | High-volume batch & real-time scoring | **~$0.00018 USD** | **$0.18 USD** |
| **Gemini Pro** | Deep executive battlecard synthesis | **~$0.00300 USD** | **$3.00 USD** |

*Production Safeguard:* Automated heuristic pre-filtering classifies accounts with zero detected vulnerabilities as Tier 4 without invoking LLM inference, keeping monthly platform operating costs below $15.00 for tens of thousands of accounts.

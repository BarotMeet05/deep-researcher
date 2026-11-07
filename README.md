# 🧭 DeepResearcher

> **Autonomous Multi-Step Evidence Retrieval & Synthesis Agent**  
> Built with **LangGraph**, **Google Gemini 2.5 Flash**, **DuckDuckGo Search**, **FastAPI SSE**, and **React + Vite**.  
> **100% Free Tier Tooling** with **Shared Key Security Protection**.

---

## 🌟 Overview

**DeepResearcher** is an agentic AI system designed to solve complex research questions that single-prompt chatbots or basic RAG systems cannot adequately address.

Instead of answering immediately with potentially hallucinated or outdated information, the agent:
1. **Deconstructs** any research prompt into focused, multi-perspective search queries (**Planner Node**).
2. **Executes live web searches** across DuckDuckGo without requiring paid API keys (**Searcher Node**).
3. **Reflects & evaluates** gathered evidence for knowledge gaps, conflicting findings, or insufficient depth (**Critic Node**).
4. **Iterates autonomously** with targeted follow-up queries if gaps are detected (Cyclic LangGraph State Machine).
5. **Synthesizes** an executive-ready Markdown dossier complete with verified source citations, trade-off comparisons, and structured tables (**Synthesizer Node**).

---

## 🏗️ Architecture & Agent Graph

```mermaid
flowchart TD
    Start([User Research Prompt]) --> Planner[Planner Node\nDeconstruct topic into search queries]
    Planner --> Searcher[Searcher Node\nDuckDuckGo Live Web Retrieval]
    Searcher --> Critic[Critic Node\nReflect on depth & identify gaps]
    
    Critic -->|Gaps Detected & Iteration <= Max| Searcher
    Critic -->|Research Sufficient or Max Iterations Reached| Synthesizer[Synthesizer Node\nDraft executive report with source citations]
    Synthesizer --> Done([End / Stream SSE to Frontend])

    classDef agent fill:#1e1e2f,stroke:#22d3ee,stroke-width:2px,color:#fff;
    classDef decision fill:#312e81,stroke:#818cf8,stroke-width:2px,color:#fff;
    classDef io fill:#0f172a,stroke:#38bdf8,stroke-width:1px,color:#fff;
    class Planner,Searcher,Synthesizer agent;
    class Critic decision;
    class Start,Done io;
```

---

## ✨ Key Features

- **Autonomous Cyclic Reflection:** Employs a cyclic LangGraph state machine with recursion guards (`max_iterations = 2`) preventing infinite loops while ensuring deep coverage.
- **100% Free-Tier Tooling:** Powered by Google's free Gemini 2.5 Flash API tier and DuckDuckGo (`ddgs`) search. Zero credit card or paid search subscriptions required.
- **Real-Time Event Streaming (SSE):** FastAPI streams live agent thoughts, queries, scraped sources, reflection critique, and the final dossier to the UI via Server-Sent Events.
- **Shared Access Key Barrier:** Protected by an `APP_ACCESS_KEY` (`X-App-Key` header / Basic Auth on `/docs`) to prevent unauthorized usage when deployed publicly.
- **Local History Persistence:** Completed research dossiers and citations are automatically stored in the browser's `localStorage` for offline reference and instant recall.
- **Executive Markdown Export:** Instant copy to clipboard, `.md` file download, and formatted tables rendering with GitHub Flavored Markdown (`remark-gfm`).

---

## 🛠️ Tech Stack

| Layer | Technologies |
|---|---|
| **Agent Core** | Python 3.11, **LangGraph**, **LangChain Google GenAI** (`gemini-2.5-flash`), **DDGS** (DuckDuckGo) |
| **Backend API** | **FastAPI**, **Uvicorn**, Server-Sent Events (`StreamingResponse`), Pydantic Settings |
| **Frontend UI** | **React 18**, **Vite 5**, **Lucide Icons**, **React-Markdown**, **Remark-GFM** |
| **Styling** | Cybernetic Dark Theme with CSS Variables & Responsive Dual-Column Grid |
| **Deployment** | **Render** (FastAPI Web Service) + **Vercel** (Vite Static Frontend) |

---

## 🚀 Quick Start (Local Development)

### 1. Prerequisites
- **Python 3.11+** installed
- **Node.js 18+** & npm installed
- A free **Google Gemini API Key** from [Google AI Studio](https://aistudio.google.com/)

### 2. Backend Setup
```bash
# 1. Clone repository
git clone https://github.com/BarotMeet05/deep-researcher.git
cd deep-researcher

# 2. Create and activate virtual environment
python -m venv .venv
# On Windows:
.venv\Scripts\activate
# On Linux/macOS:
# source .venv/bin/activate

# 3. Install backend dependencies
pip install -r requirements.txt

# 4. Configure environment
cp .env.example .env
# Edit .env and paste your GEMINI_API_KEY and choose an APP_ACCESS_KEY (e.g. researcher2026)

# 5. Start the FastAPI server
cd backend
uvicorn app.main:app --reload --port 8000
```
*Backend health check will be live at `http://127.0.0.1:8000/health`.*  
*Protected API documentation available at `http://127.0.0.1:8000/docs` (enter your access passcode).*

### 3. Frontend Setup
Open a separate terminal:
```bash
cd frontend

# Install dependencies
npm install

# Start Vite dev server
npm run dev
```
*Frontend will be running at `http://localhost:5173` with proxy configured to backend `localhost:8000`.*

---

## 🔒 Security Configuration

To prevent unauthorized public users from draining your Gemini API quota:
1. Set `APP_ACCESS_KEY="your-secret-passcode"` in your backend `.env` (or Render Environment Variables).
2. All `/api/v1/*` requests require the header `X-App-Key: your-secret-passcode`.
3. The React frontend provides a built-in Passcode modal to enter and remember this key in your browser.
4. `/docs`, `/redoc`, and `/openapi.json` are secured with HTTP Basic Auth challenge (leave username blank or enter anything, and provide your passcode as the password).

---

## 📦 Deployment

### Deploy Backend on Render
1. Push this repository to GitHub.
2. Create a new **Web Service** on [Render](https://render.com).
3. Connect your GitHub repository.
4. Set the following settings:
   - **Environment:** `Python 3`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `cd backend && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
5. Add Environment Variables:
   - `GEMINI_API_KEY`: `<your-gemini-api-key>`
   - `APP_ACCESS_KEY`: `<your-chosen-passcode>`
   - `ALLOWED_ORIGINS`: `*` (or your Vercel frontend URL)

### Deploy Frontend on Vercel
1. Create a new project on [Vercel](https://vercel.com) and import the repository.
2. Set **Root Directory** to `frontend`.
3. Add Environment Variable:
   - `VITE_API_URL`: `https://<your-render-backend-url>.onrender.com`
4. Click **Deploy**.

---

## 📄 License
MIT License. Built for advanced agentic AI experimentation and portfolio demonstration.

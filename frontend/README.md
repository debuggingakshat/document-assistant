# Frontend — Document Assistant

Web client for **Document Assistant**, the AI equity research copilot for **Meridian Research**. Built with React 19, TypeScript, Vite, Tailwind CSS, and Lucide icons.

---

## Features

- **Analyst Chat Interface**: Streamed responses with real-time token rendering and PydanticAI / SSE pipeline stage tracking.
- **Citation Badges & Trust Drawer**: Every factual statement links directly to its verified SEC 10-K filing passage, page number, and accession number via an interactive slide-over drawer and inspect sheet.
- **Financial Table Renderer**: Native Markdown table parser rendering crisp, rectangular balance sheets and revenue breakdowns with currency formatting.
- **Multi-Thread Management**: Complete thread history, conversation switching, and auto-generated titles persisted to Supabase Postgres.
- **Auth & Session Management**: Supabase Auth integration with protected route guards, login, and registration flows.
- **Theme Support**: Seamless Dark Mode and Light Mode toggling with custom financial-palette styling.

---

## Getting Started

### Prerequisites

- Node.js 18+ (Node 20+ recommended)
- npm or pnpm

### Setup

```bash
cd frontend
cp .env.example .env   # Verify VITE_API_BASE_URL and Supabase credentials
npm install
```

### Environment Variables

| Variable | Description |
| --- | --- |
| `VITE_API_BASE_URL` | Base URL of FastAPI backend (default: `http://localhost:8000`) |
| `VITE_SUPABASE_URL` | Supabase project URL |
| `VITE_SUPABASE_ANON_KEY` | Supabase anonymous / public browser key |

### Development Server

```bash
npm run dev
```

App runs at: `http://localhost:5173`

---

## Project Structure

```text
frontend/src/
├── components/
│   ├── chat/
│   │   ├── ChatArea.tsx                 # Main message stream and scroll container
│   │   ├── ChatLayout.tsx               # Responsive layout wrapper with sidebar
│   │   ├── FinancialTable.tsx           # Formatted financial table component
│   │   ├── MessageInput.tsx             # Multiline query input with submit controls
│   │   ├── MessageItem.tsx              # Message bubble with citation chips
│   │   ├── PipelineStatusIndicator.tsx  # Retrieval/Grounding status indicator
│   │   ├── Sidebar.tsx                  # Thread drawer, search, and session info
│   │   ├── SourcePassageDrawer.tsx      # Slide-out citation excerpt drawer
│   │   ├── SourcePassageSheet.tsx       # Detailed filing passage modal
│   │   └── ThemeToggle.tsx              # Dark/light mode switcher
│   ├── ui/                              # Shared Tailwind UI primitives
│   └── ProtectedRoute.tsx               # Supabase Auth session gate
├── lib/                                 # API clients, auth context, Supabase client
├── pages/                               # Route views (HomePage, ChatPage, LoginPage, SignUpPage)
├── index.css                            # Core CSS variables, typography, and theme tokens
└── main.tsx                             # Application entrypoint
```

---

## Quality Checks

```bash
# Type check and production build
npm run build

# Linting
npm run lint
```

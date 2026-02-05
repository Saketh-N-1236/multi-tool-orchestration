# Multi-Tool Orchestration Frontend

React + Vite frontend application for the Multi-Tool Orchestration system.

## Features

- **Chat Interface**: Interactive chat with the AI assistant, showing tool calls and results
- **Analytics Dashboard**: Real-time monitoring and analytics visualization
- **Document Management**: Upload and manage documents in vector collections
- **Tools Explorer**: Browse and explore available MCP tools

## Tech Stack

- **React 18** with TypeScript
- **Vite** for build tooling
- **React Router** for navigation
- **Chart.js** for data visualization
- **Axios** for API communication
- **Lucide React** for icons

## Getting Started

### Prerequisites

- Node.js 18+ and npm/yarn

### Installation

```bash
cd frontend
npm install
```

### Development

```bash
npm run dev
```

The application will be available at `http://localhost:3000`

### Build

```bash
npm run build
```

The production build will be in the `dist` directory.

### Preview Production Build

```bash
npm run preview
```

## Project Structure

```
frontend/
├── src/
│   ├── components/
│   │   └── Layout/          # Header, Sidebar, MainLayout
│   ├── pages/               # Page components
│   │   ├── ChatPage.tsx
│   │   ├── AnalyticsPage.tsx
│   │   ├── DocumentsPage.tsx
│   │   └── ToolsPage.tsx
│   ├── services/
│   │   └── api.ts           # API client
│   ├── types/
│   │   └── api.ts           # TypeScript types
│   ├── App.tsx
│   ├── main.tsx
│   └── index.css
├── public/
│   └── company_logo.png
└── package.json
```

## API Integration

The frontend communicates with the FastAPI backend running on `http://localhost:8000`. The Vite proxy is configured to forward `/api` requests to the backend.

## Environment Variables

Create a `.env` file in the `frontend` directory if needed:

```env
VITE_API_BASE_URL=http://localhost:8000
```

## Features Overview

### Chat Page
- Real-time chat interface
- Message history
- Tool call visualization
- Message details panel

### Analytics Page
- Overview statistics
- Tool usage charts
- Response time metrics
- Time series visualization

### Documents Page
- Upload documents to collections
- Manage collections
- Search functionality

### Tools Page
- Browse available tools
- Filter by server
- View tool details
- Server status monitoring

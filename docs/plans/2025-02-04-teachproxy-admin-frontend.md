# TeachProxy Admin Frontend Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a modern React-based admin dashboard to replace Streamlit, with full CRUD operations for students, conversations, rules, and weekly prompts.

**Architecture:** 
- Backend: Extend FastAPI with `/admin/*` REST endpoints using existing `db_utils_v2.py` logic
- Frontend: React 18 + TypeScript + Vite + shadcn/ui + TanStack Query + React Router
- Auth: Bearer token (Admin Token) stored in localStorage
- State: Server state via TanStack Query, UI state via React hooks

**Tech Stack:** React 18, TypeScript, Vite, shadcn/ui, Tailwind CSS, TanStack Query, Axios, Recharts

---

## Overview

This plan implements a complete admin dashboard in two phases:
1. **Phase 1:** Backend Admin API (FastAPI endpoints)
2. **Phase 2:** Frontend React Application

Total estimated tasks: ~35 bite-sized steps

---

## Phase 1: Backend Admin API

### Task 1: Create Admin API Router Structure

**Files:**
- Create: `gateway/app/api/admin/__init__.py`
- Create: `gateway/app/api/admin/router.py`
- Modify: `gateway/app/main.py` (include admin router)

**Step 1: Create admin router module**

```python
# gateway/app/api/admin/__init__.py
from .router import router

__all__ = ["router"]
```

**Step 2: Create main admin router**

```python
# gateway/app/api/admin/router.py
from fastapi import APIRouter, Depends
from gateway.app.middleware.auth import require_admin

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])

# Sub-routers will be included here
from . import students, conversations, rules, weekly_prompts, dashboard

router.include_router(students.router, prefix="/students", tags=["admin-students"])
router.include_router(conversations.router, prefix="/conversations", tags=["admin-conversations"])
router.include_router(rules.router, prefix="/rules", tags=["admin-rules"])
router.include_router(weekly_prompts.router, prefix="/weekly-prompts", tags=["admin-weekly-prompts"])
router.include_router(dashboard.router, prefix="/dashboard", tags=["admin-dashboard"])
```

**Step 3: Include admin router in main.py**

Modify `gateway/app/main.py` after line 171:
```python
from gateway.app.api.admin import router as admin_router
app.include_router(admin_router)
```

**Step 4: Test router loads**

Run: `cd /Users/wangxq/Documents/python && python -c "from gateway.app.main import app; print('Admin router loaded:', any(r.path.startswith('/admin') for r in app.routes))"`

Expected: `Admin router loaded: True`

**Step 5: Commit**

```bash
git add gateway/app/api/admin/ gateway/app/main.py
git commit -m "feat(admin): add admin API router structure"
```

---

### Task 2: Dashboard Stats Endpoint

**Files:**
- Create: `gateway/app/api/admin/dashboard.py`
- Test: `curl http://localhost:8000/admin/dashboard/stats -H "Authorization: Bearer <token>"`

**Step 1: Write endpoint**

```python
# gateway/app/api/admin/dashboard.py
from fastapi import APIRouter
from typing import Any
from admin.db_utils_v2 import get_dashboard_stats, get_recent_activity

router = APIRouter()

@router.get("/stats")
async def dashboard_stats() -> dict[str, Any]:
    """Get dashboard statistics."""
    return get_dashboard_stats()

@router.get("/activity")
async def dashboard_activity(days: int = 7) -> list[dict[str, Any]]:
    """Get recent activity for charts."""
    return get_recent_activity(days=days)
```

**Step 2: Test endpoint**

Start server: `uv run uvicorn gateway.app.main:app --reload &`

Test: `curl -s http://localhost:8000/admin/dashboard/stats -H "Authorization: Bearer _D9PyQ6EvlyNI9Rs_ZdHOijGQQ_6dI2YuvdosTcl4Bc" | head -c 200`

Expected: JSON with stats fields

**Step 3: Commit**

```bash
git add gateway/app/api/admin/dashboard.py
git commit -m "feat(admin): add dashboard stats endpoint"
```

---

### Task 3: Students API Endpoints

**Files:**
- Create: `gateway/app/api/admin/students.py`
- Uses: `admin.db_utils_v2` functions

**Step 1: Define schemas**

```python
# gateway/app/api/admin/students.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from admin.db_utils_v2 import (
    get_all_students, create_student, get_student_by_id,
    update_student_quota, reset_student_quota, 
    regenerate_student_api_key, delete_student,
    get_student_quota_stats
)

router = APIRouter()

class StudentCreate(BaseModel):
    name: str
    email: str
    quota: int = 10000

class StudentUpdateQuota(BaseModel):
    quota: int

class StudentResponse(BaseModel):
    id: str
    name: str
    email: str
    current_week_quota: int
    used_quota: int
    created_at: Optional[str]
```

**Step 2: Implement endpoints**

```python
@router.get("")
async def list_students() -> list[dict]:
    """List all students."""
    return get_all_students()

@router.post("")
async def create_new_student(data: StudentCreate) -> dict:
    """Create a new student."""
    student, api_key = create_student(
        name=data.name,
        email=data.email,
        quota=data.quota
    )
    return {
        "student": student,
        "api_key": api_key
    }

@router.get("/{student_id}")
async def get_student(student_id: str) -> dict:
    """Get student by ID."""
    student = get_student_by_id(student_id)
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    return student

@router.put("/{student_id}/quota")
async def update_quota(student_id: str, data: StudentUpdateQuota) -> dict:
    """Update student quota."""
    success = update_student_quota(student_id, data.quota)
    if not success:
        raise HTTPException(status_code=404, detail="Student not found")
    return {"success": True}

@router.post("/{student_id}/reset-quota")
async def reset_quota(student_id: str) -> dict:
    """Reset student used quota."""
    success = reset_student_quota(student_id)
    if not success:
        raise HTTPException(status_code=404, detail="Student not found")
    return {"success": True}

@router.post("/{student_id}/regenerate-key")
async def regen_key(student_id: str) -> dict:
    """Regenerate API key."""
    new_key = regenerate_student_api_key(student_id)
    if not new_key:
        raise HTTPException(status_code=404, detail="Student not found")
    return {"api_key": new_key}

@router.delete("/{student_id}")
async def remove_student(student_id: str) -> dict:
    """Delete student."""
    success = delete_student(student_id)
    if not success:
        raise HTTPException(status_code=404, detail="Student not found")
    return {"success": True}

@router.get("/{student_id}/stats")
async def student_stats(student_id: str) -> dict:
    """Get student quota statistics."""
    stats = get_student_quota_stats(student_id)
    if not stats:
        raise HTTPException(status_code=404, detail="Student not found")
    return stats
```

**Step 3: Test endpoints**

```bash
curl -s http://localhost:8000/admin/students -H "Authorization: Bearer <token>" | jq '. | length'
```

Expected: Number of students (e.g., 5)

**Step 4: Commit**

```bash
git add gateway/app/api/admin/students.py
git commit -m "feat(admin): add students CRUD endpoints"
```

---

### Task 4: Conversations API Endpoint

**Files:**
- Create: `gateway/app/api/admin/conversations.py`

**Step 1: Implement endpoint**

```python
# gateway/app/api/admin/conversations.py
from fastapi import APIRouter, Query
from typing import Optional
from datetime import datetime
from admin.db_utils_v2 import get_conversations, get_conversation_count

router = APIRouter()

@router.get("")
async def list_conversations(
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    student_id: Optional[str] = None,
    action: Optional[str] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None
) -> dict:
    """List conversations with pagination and filtering."""
    conversations = get_conversations(
        limit=limit,
        offset=offset,
        student_id=student_id,
        action=action,
        start_date=start_date,
        end_date=end_date
    )
    total = get_conversation_count(student_id=student_id, action=action)
    
    return {
        "items": conversations,
        "total": total,
        "limit": limit,
        "offset": offset
    }
```

**Step 2: Test**

```bash
curl -s "http://localhost:8000/admin/conversations?limit=10" -H "Authorization: Bearer <token>" | jq '.total'
```

**Step 3: Commit**

```bash
git add gateway/app/api/admin/conversations.py
git commit -m "feat(admin): add conversations list endpoint"
```

---

### Task 5: Rules API Endpoints

**Files:**
- Create: `gateway/app/api/admin/rules.py`

**Step 1: Implement endpoints**

```python
# gateway/app/api/admin/rules.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from admin.db_utils_v2 import (
    get_all_rules, create_rule, update_rule, 
    delete_rule, toggle_rule_enabled
)
from gateway.app.services.rule_service import reload_rules

router = APIRouter()

class RuleCreate(BaseModel):
    pattern: str
    rule_type: str  # "block" or "guide"
    message: str
    active_weeks: str = "1-16"
    enabled: bool = True

class RuleUpdate(BaseModel):
    pattern: Optional[str] = None
    rule_type: Optional[str] = None
    message: Optional[str] = None
    active_weeks: Optional[str] = None
    enabled: Optional[bool] = None

@router.get("")
async def list_rules() -> list[dict]:
    """List all custom rules."""
    return get_all_rules()

@router.post("")
async def create_new_rule(data: RuleCreate) -> dict:
    """Create a new rule."""
    rule = create_rule(**data.dict())
    return rule

@router.put("/{rule_id}")
async def update_existing_rule(rule_id: int, data: RuleUpdate) -> dict:
    """Update a rule."""
    success = update_rule(rule_id, **{k: v for k, v in data.dict().items() if v is not None})
    if not success:
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"success": True}

@router.delete("/{rule_id}")
async def remove_rule(rule_id: int) -> dict:
    """Delete a rule."""
    success = delete_rule(rule_id)
    if not success:
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"success": True}

@router.post("/{rule_id}/toggle")
async def toggle_rule(rule_id: int) -> dict:
    """Toggle rule enabled state."""
    enabled = toggle_rule_enabled(rule_id)
    if enabled is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    return {"enabled": enabled}

@router.post("/reload-cache")
async def reload_rules_cache() -> dict:
    """Reload rules cache."""
    reload_rules()
    return {"success": True}
```

**Step 2: Test**

```bash
curl -s http://localhost:8000/admin/rules -H "Authorization: Bearer <token>" | jq '. | length'
```

**Step 3: Commit**

```bash
git add gateway/app/api/admin/rules.py
git commit -m "feat(admin): add rules CRUD endpoints"
```

---

### Task 6: Weekly Prompts API Endpoints

**Files:**
- Create: `gateway/app/api/admin/weekly_prompts.py`

**Step 1: Implement endpoints**

```python
# gateway/app/api/admin/weekly_prompts.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
from admin.db_utils_v2 import (
    get_all_weekly_prompts, get_prompt_by_week, 
    get_current_week_prompt, create_or_update_weekly_prompt,
    delete_weekly_prompt
)

router = APIRouter()

class WeeklyPromptCreate(BaseModel):
    week_start: int
    week_end: int
    system_prompt: str
    description: Optional[str] = None
    is_active: bool = True

@router.get("")
async def list_prompts() -> list[dict]:
    """List all weekly prompts."""
    return get_all_weekly_prompts()

@router.get("/current")
async def get_current() -> Optional[dict]:
    """Get current week prompt."""
    return get_current_week_prompt()

@router.get("/week/{week_number}")
async def get_by_week(week_number: int) -> Optional[dict]:
    """Get prompt for specific week."""
    return get_prompt_by_week(week_number)

@router.post("")
async def create_or_update(data: WeeklyPromptCreate) -> dict:
    """Create or update weekly prompt."""
    prompt = create_or_update_weekly_prompt(**data.dict())
    return prompt

@router.delete("/{prompt_id}")
async def remove_prompt(prompt_id: int) -> dict:
    """Delete weekly prompt."""
    success = delete_weekly_prompt(prompt_id)
    if not success:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return {"success": True}
```

**Step 2: Commit**

```bash
git add gateway/app/api/admin/weekly_prompts.py
git commit -m "feat(admin): add weekly prompts CRUD endpoints"
```

---

## Phase 2: Frontend React Application

### Task 7: Initialize Vite + React + TypeScript Project

**Files:**
- Create: `web/` directory structure

**Step 1: Create project**

```bash
cd /Users/wangxq/Documents/python
npm create vite@latest web -- --template react-ts
cd web
npm install
```

**Step 2: Install dependencies**

```bash
npm install @tanstack/react-query axios react-router-dom lucide-react
npm install -D tailwindcss postcss autoprefixer @types/node
```

**Step 3: Initialize Tailwind**

```bash
npx tailwindcss init -p
```

Update `tailwind.config.js`:
```javascript
/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {},
  },
  plugins: [],
}
```

Update `src/index.css`:
```css
@tailwind base;
@tailwind components;
@tailwind utilities;
```

**Step 4: Test dev server**

```bash
npm run dev &
sleep 3
curl -s http://localhost:5173 | grep -o "Vite \+ React" | head -1
```

Expected: `Vite + React`

**Step 5: Commit**

```bash
git add web/
git commit -m "feat(web): initialize vite react typescript project"
```

---

### Task 8: Setup shadcn/ui

**Files:**
- Modify: `web/package.json`
- Create: `web/components.json`

**Step 1: Initialize shadcn**

```bash
cd /Users/wangxq/Documents/python/web
npx shadcn@latest init -y -d
```

**Step 2: Install base components**

```bash
npx shadcn add button card table badge dialog input label select tabs
```

**Step 3: Test component**

Create `src/test-shadcn.tsx`:
```tsx
import { Button } from "@/components/ui/button"

export function TestShadcn() {
  return <Button>Test Button</Button>
}
```

Verify imports work in `src/App.tsx` temporarily.

**Step 4: Commit**

```bash
git add web/
git commit -m "feat(web): setup shadcn/ui with base components"
```

---

### Task 9: Create API Client and Types

**Files:**
- Create: `web/src/lib/api.ts`
- Create: `web/src/types/index.ts`
- Create: `web/src/lib/config.ts`

**Step 1: Create types**

```typescript
// web/src/types/index.ts
export interface Student {
  id: string;
  name: string;
  email: string;
  current_week_quota: number;
  used_quota: number;
  created_at: string;
  provider_type?: string;
}

export interface Conversation {
  id: number;
  student_id: string;
  timestamp: string;
  prompt_text: string;
  response_text: string;
  tokens_used: number;
  action_taken: string;
  rule_triggered?: string;
  week_number: number;
  model?: string;
}

export interface Rule {
  id: number;
  pattern: string;
  rule_type: 'block' | 'guide';
  message: string;
  active_weeks: string;
  enabled: boolean;
}

export interface WeeklyPrompt {
  id: number;
  week_start: number;
  week_end: number;
  system_prompt: string;
  description?: string;
  is_active: boolean;
  created_at?: string;
  updated_at?: string;
}

export interface DashboardStats {
  students: number;
  conversations: number;
  conversations_today: number;
  rules: number;
  blocked: number;
  total_tokens: number;
  tokens_today: number;
  quota_usage_rate: number;
  current_week: number;
}
```

**Step 2: Create API client**

```typescript
// web/src/lib/api.ts
import axios from 'axios';
import { Student, Conversation, Rule, WeeklyPrompt, DashboardStats } from '@/types';

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

const api = axios.create({
  baseURL: `${API_BASE}/admin`,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add auth token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('admin_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('admin_token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);

// Dashboard API
export const dashboardApi = {
  getStats: () => api.get<DashboardStats>('/dashboard/stats').then(r => r.data),
  getActivity: (days = 7) => api.get('/dashboard/activity', { params: { days } }).then(r => r.data),
};

// Students API
export const studentsApi = {
  list: () => api.get<Student[]>('/students').then(r => r.data),
  create: (data: { name: string; email: string; quota: number }) => 
    api.post('/students', data).then(r => r.data),
  updateQuota: (id: string, quota: number) => 
    api.put(`/students/${id}/quota`, { quota }).then(r => r.data),
  resetQuota: (id: string) => 
    api.post(`/students/${id}/reset-quota`).then(r => r.data),
  regenerateKey: (id: string) => 
    api.post(`/students/${id}/regenerate-key`).then(r => r.data),
  delete: (id: string) => 
    api.delete(`/students/${id}`).then(r => r.data),
  getStats: (id: string) => 
    api.get(`/students/${id}/stats`).then(r => r.data),
};

// Conversations API
export const conversationsApi = {
  list: (params?: { limit?: number; offset?: number; student_id?: string; action?: string }) =>
    api.get<{ items: Conversation[]; total: number }>('/conversations', { params }).then(r => r.data),
};

// Rules API
export const rulesApi = {
  list: () => api.get<Rule[]>('/rules').then(r => r.data),
  create: (data: Omit<Rule, 'id'>) => api.post('/rules', data).then(r => r.data),
  update: (id: number, data: Partial<Rule>) => api.put(`/rules/${id}`, data).then(r => r.data),
  delete: (id: number) => api.delete(`/rules/${id}`).then(r => r.data),
  toggle: (id: number) => api.post(`/rules/${id}/toggle`).then(r => r.data),
  reloadCache: () => api.post('/rules/reload-cache').then(r => r.data),
};

// Weekly Prompts API
export const promptsApi = {
  list: () => api.get<WeeklyPrompt[]>('/weekly-prompts').then(r => r.data),
  getCurrent: () => api.get<WeeklyPrompt | null>('/weekly-prompts/current').then(r => r.data),
  create: (data: Omit<WeeklyPrompt, 'id'>) => api.post('/weekly-prompts', data).then(r => r.data),
  delete: (id: number) => api.delete(`/weekly-prompts/${id}`).then(r => r.data),
};

export default api;
```

**Step 3: Commit**

```bash
git add web/src/lib/api.ts web/src/types/index.ts
git commit -m "feat(web): add API client and TypeScript types"
```

---

### Task 10: Setup React Query Provider

**Files:**
- Create: `web/src/providers/query-provider.tsx`
- Modify: `web/src/main.tsx`

**Step 1: Create provider**

```tsx
// web/src/providers/query-provider.tsx
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { ReactQueryDevtools } from '@tanstack/react-query-devtools';
import { ReactNode } from 'react';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30 * 1000, // 30 seconds
      refetchOnWindowFocus: true,
      retry: 1,
    },
  },
});

export function QueryProvider({ children }: { children: ReactNode }) {
  return (
    <QueryClientProvider client={queryClient}>
      {children}
      <ReactQueryDevtools initialIsOpen={false} />
    </QueryClientProvider>
  );
}
```

**Step 2: Update main.tsx**

```tsx
// web/src/main.tsx
import React from 'react';
import ReactDOM from 'react-dom/client';
import { QueryProvider } from './providers/query-provider';
import App from './App';
import './index.css';

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryProvider>
      <App />
    </QueryProvider>
  </React.StrictMode>
);
```

**Step 3: Commit**

```bash
git add web/src/providers/ web/src/main.tsx
git commit -m "feat(web): setup react query provider"
```

---

### Task 11: Create Layout Component

**Files:**
- Create: `web/src/components/layout.tsx`
- Create: `web/src/components/sidebar.tsx`
- Create: `web/src/components/header.tsx`

**Step 1: Create Sidebar**

```tsx
// web/src/components/sidebar.tsx
import { Link, useLocation } from 'react-router-dom';
import { 
  LayoutDashboard, Users, MessageSquare, Shield, 
  Calendar, Settings, Menu, X 
} from 'lucide-react';
import { Button } from '@/components/ui/button';
import { useState } from 'react';

const navItems = [
  { icon: LayoutDashboard, label: 'Dashboard', path: '/' },
  { icon: Users, label: 'Students', path: '/students' },
  { icon: MessageSquare, label: 'Conversations', path: '/conversations' },
  { icon: Shield, label: 'Rules', path: '/rules' },
  { icon: Calendar, label: 'Weekly Prompts', path: '/weekly-prompts' },
];

export function Sidebar() {
  const location = useLocation();
  const [collapsed, setCollapsed] = useState(false);

  return (
    <aside className={`bg-slate-900 text-white transition-all ${collapsed ? 'w-16' : 'w-64'}`}>
      <div className="p-4 flex items-center justify-between">
        {!collapsed && <h1 className="text-xl font-bold">TeachProxy</h1>}
        <Button variant="ghost" size="icon" onClick={() => setCollapsed(!collapsed)}>
          {collapsed ? <Menu size={20} /> : <X size={20} />}
        </Button>
      </div>
      
      <nav className="mt-8">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = location.pathname === item.path;
          
          return (
            <Link
              key={item.path}
              to={item.path}
              className={`flex items-center px-4 py-3 transition-colors ${
                isActive ? 'bg-slate-800 text-blue-400' : 'hover:bg-slate-800'
              }`}
            >
              <Icon size={20} />
              {!collapsed && <span className="ml-3">{item.label}</span>}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
```

**Step 2: Create Layout**

```tsx
// web/src/components/layout.tsx
import { Outlet } from 'react-router-dom';
import { Sidebar } from './sidebar';

export function Layout() {
  return (
    <div className="flex h-screen bg-slate-50">
      <Sidebar />
      <main className="flex-1 overflow-auto">
        <div className="p-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
```

**Step 3: Commit**

```bash
git add web/src/components/layout.tsx web/src/components/sidebar.tsx
git commit -m "feat(web): add layout and sidebar components"
```

---

### Task 12: Create Login Page

**Files:**
- Create: `web/src/pages/login.tsx`
- Modify: `web/src/App.tsx`

**Step 1: Create login page**

```tsx
// web/src/pages/login.tsx
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { AlertCircle } from 'lucide-react';
import axios from 'axios';

export function LoginPage() {
  const [token, setToken] = useState('');
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      // Verify token by making a test request
      const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';
      await axios.get(`${API_BASE}/admin/dashboard/stats`, {
        headers: { Authorization: `Bearer ${token}` },
      });

      localStorage.setItem('admin_token', token);
      navigate('/');
    } catch {
      setError('Invalid admin token');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-100">
      <Card className="w-full max-w-md">
        <CardHeader>
          <CardTitle className="text-2xl text-center">TeachProxy Admin</CardTitle>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div>
              <Label htmlFor="token">Admin Token</Label>
              <Input
                id="token"
                type="password"
                value={token}
                onChange={(e) => setToken(e.target.value)}
                placeholder="Enter your admin token"
                required
              />
            </div>

            {error && (
              <div className="flex items-center gap-2 text-red-600 text-sm">
                <AlertCircle size={16} />
                {error}
              </div>
            )}

            <Button type="submit" className="w-full" disabled={loading}>
              {loading ? 'Verifying...' : 'Login'}
            </Button>
          </form>
        </CardContent>
      </Card>
    </div>
  );
}
```

**Step 2: Update App.tsx with routing**

```tsx
// web/src/App.tsx
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { Layout } from '@/components/layout';
import { LoginPage } from '@/pages/login';
import { DashboardPage } from '@/pages/dashboard';
import { StudentsPage } from '@/pages/students';
import { ConversationsPage } from '@/pages/conversations';
import { RulesPage } from '@/pages/rules';
import { WeeklyPromptsPage } from '@/pages/weekly-prompts';

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const token = localStorage.getItem('admin_token');
  return token ? <>{children}</> : <Navigate to="/login" replace />;
}

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/"
          element={
            <ProtectedRoute>
              <Layout />
            </ProtectedRoute>
          }
        >
          <Route index element={<DashboardPage />} />
          <Route path="students" element={<StudentsPage />} />
          <Route path="conversations" element={<ConversationsPage />} />
          <Route path="rules" element={<RulesPage />} />
          <Route path="weekly-prompts" element={<WeeklyPromptsPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
```

**Step 3: Commit**

```bash
git add web/src/pages/login.tsx web/src/App.tsx
git commit -m "feat(web): add login page and routing"
```

---

### Task 13: Create Dashboard Page

**Files:**
- Create: `web/src/pages/dashboard.tsx`
- Install: recharts

**Step 1: Install recharts**

```bash
cd /Users/wangxq/Documents/python/web
npm install recharts
```

**Step 2: Create dashboard page**

```tsx
// web/src/pages/dashboard.tsx
import { useQuery } from '@tanstack/react-query';
import { dashboardApi } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Users, MessageSquare, Coins, Shield } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar } from 'recharts';

function StatCard({ title, value, icon: Icon, subtitle }: { title: string; value: string | number; icon: any; subtitle?: string }) {
  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between pb-2">
        <CardTitle className="text-sm font-medium">{title}</CardTitle>
        <Icon className="h-4 w-4 text-muted-foreground" />
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{value}</div>
        {subtitle && <p className="text-xs text-muted-foreground">{subtitle}</p>}
      </CardContent>
    </Card>
  );
}

export function DashboardPage() {
  const { data: stats, isLoading } = useQuery({
    queryKey: ['dashboard', 'stats'],
    queryFn: dashboardApi.getStats,
  });

  const { data: activity } = useQuery({
    queryKey: ['dashboard', 'activity'],
    queryFn: () => dashboardApi.getActivity(7),
  });

  if (isLoading) {
    return <div>Loading...</div>;
  }

  return (
    <div className="space-y-6">
      <h2 className="text-3xl font-bold">Dashboard</h2>
      
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <StatCard 
          title="Total Students" 
          value={stats?.students || 0} 
          icon={Users}
        />
        <StatCard 
          title="Conversations Today" 
          value={stats?.conversations_today || 0} 
          icon={MessageSquare}
          subtitle={`Total: ${stats?.conversations || 0}`}
        />
        <StatCard 
          title="Tokens Today" 
          value={(stats?.tokens_today || 0).toLocaleString()} 
          icon={Coins}
          subtitle={`Total: ${(stats?.total_tokens || 0).toLocaleString()}`}
        />
        <StatCard 
          title="Blocked Requests" 
          value={stats?.blocked || 0} 
          icon={Shield}
        />
      </div>

      {activity && activity.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>Recent Activity (7 days)</CardTitle>
          </CardHeader>
          <CardContent>
            <ResponsiveContainer width="100%" height={300}>
              <LineChart data={activity}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="date" />
                <YAxis />
                <Tooltip />
                <Line type="monotone" dataKey="conversations" stroke="#8884d8" />
                <Line type="monotone" dataKey="tokens" stroke="#82ca9d" />
              </LineChart>
            </ResponsiveContainer>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
```

**Step 3: Commit**

```bash
git add web/src/pages/dashboard.tsx
git commit -m "feat(web): add dashboard page with stats and charts"
```

---

### Task 14: Create Students Page

**Files:**
- Create: `web/src/pages/students.tsx`

**Step 1: Create students page**

```tsx
// web/src/pages/students.tsx
import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { studentsApi } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Plus, Key, RotateCcw, Trash2 } from 'lucide-react';
import type { Student } from '@/types';

export function StudentsPage() {
  const queryClient = useQueryClient();
  const [search, setSearch] = useState('');
  const [newStudent, setNewStudent] = useState({ name: '', email: '', quota: 10000 });
  const [createdKey, setCreatedKey] = useState<string | null>(null);

  const { data: students, isLoading } = useQuery({
    queryKey: ['students'],
    queryFn: studentsApi.list,
  });

  const createMutation = useMutation({
    mutationFn: studentsApi.create,
    onSuccess: (data) => {
      setCreatedKey(data.api_key);
      queryClient.invalidateQueries({ queryKey: ['students'] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: studentsApi.delete,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['students'] }),
  });

  const regenerateMutation = useMutation({
    mutationFn: studentsApi.regenerateKey,
    onSuccess: (data) => {
      setCreatedKey(data.api_key);
    },
  });

  const filteredStudents = students?.filter((s: Student) => 
    s.name.toLowerCase().includes(search.toLowerCase()) ||
    s.email.toLowerCase().includes(search.toLowerCase())
  );

  const getUsageBadge = (used: number, quota: number) => {
    const pct = quota > 0 ? (used / quota) * 100 : 0;
    if (pct >= 100) return <Badge variant="destructive">Exhausted</Badge>;
    if (pct >= 80) return <Badge variant="secondary">Warning</Badge>;
    if (used === 0) return <Badge variant="outline">Unused</Badge>;
    return <Badge className="bg-green-500">Normal</Badge>;
  };

  if (isLoading) return <div>Loading...</div>;

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-3xl font-bold">Students</h2>
        <Dialog>
          <DialogTrigger asChild>
            <Button><Plus className="mr-2 h-4 w-4" /> Add Student</Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Create New Student</DialogTitle>
            </DialogHeader>
            <div className="space-y-4 py-4">
              <div>
                <Label>Name</Label>
                <Input 
                  value={newStudent.name} 
                  onChange={e => setNewStudent({...newStudent, name: e.target.value})}
                />
              </div>
              <div>
                <Label>Email</Label>
                <Input 
                  type="email"
                  value={newStudent.email} 
                  onChange={e => setNewStudent({...newStudent, email: e.target.value})}
                />
              </div>
              <div>
                <Label>Weekly Quota</Label>
                <Input 
                  type="number"
                  value={newStudent.quota} 
                  onChange={e => setNewStudent({...newStudent, quota: parseInt(e.target.value)})}
                />
              </div>
              <Button 
                onClick={() => createMutation.mutate(newStudent)}
                disabled={!newStudent.name || !newStudent.email}
              >
                Create
              </Button>
            </div>
          </DialogContent>
        </Dialog>
      </div>

      {createdKey && (
        <Card className="bg-yellow-50 border-yellow-200">
          <CardContent className="pt-6">
            <p className="font-semibold text-yellow-800 mb-2">API Key Generated (save this!)</p>
            <code className="bg-yellow-100 px-2 py-1 rounded">{createdKey}</code>
            <Button variant="ghost" size="sm" onClick={() => setCreatedKey(null)} className="ml-2">Dismiss</Button>
          </CardContent>
        </Card>
      )}

      <Input 
        placeholder="Search students..." 
        value={search}
        onChange={e => setSearch(e.target.value)}
        className="max-w-sm"
      />

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Email</TableHead>
                <TableHead>Quota</TableHead>
                <TableHead>Used</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filteredStudents?.map((student: Student) => (
                <TableRow key={student.id}>
                  <TableCell className="font-medium">{student.name}</TableCell>
                  <TableCell>{student.email}</TableCell>
                  <TableCell>{student.current_week_quota.toLocaleString()}</TableCell>
                  <TableCell>{student.used_quota.toLocaleString()}</TableCell>
                  <TableCell>{getUsageBadge(student.used_quota, student.current_week_quota)}</TableCell>
                  <TableCell>
                    <div className="flex gap-2">
                      <Button 
                        variant="ghost" 
                        size="icon"
                        onClick={() => regenerateMutation.mutate(student.id)}
                        title="Regenerate API Key"
                      >
                        <Key className="h-4 w-4" />
                      </Button>
                      <Button 
                        variant="ghost" 
                        size="icon"
                        onClick={() => studentsApi.resetQuota(student.id)}
                        title="Reset Quota"
                      >
                        <RotateCcw className="h-4 w-4" />
                      </Button>
                      <Button 
                        variant="ghost" 
                        size="icon"
                        onClick={() => deleteMutation.mutate(student.id)}
                        title="Delete"
                      >
                        <Trash2 className="h-4 w-4 text-red-500" />
                      </Button>
                    </div>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
```

**Step 2: Commit**

```bash
git add web/src/pages/students.tsx
git commit -m "feat(web): add students management page"
```

---

### Task 15: Create Remaining Pages (Conversations, Rules, Weekly Prompts)

**Files:**
- Create: `web/src/pages/conversations.tsx`
- Create: `web/src/pages/rules.tsx`
- Create: `web/src/pages/weekly-prompts.tsx`

**Step 1: Create conversations page**

```tsx
// web/src/pages/conversations.tsx
import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { conversationsApi } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import type { Conversation } from '@/types';

export function ConversationsPage() {
  const [filters, setFilters] = useState({ action: '', student_id: '' });
  
  const { data, isLoading } = useQuery({
    queryKey: ['conversations', filters],
    queryFn: () => conversationsApi.list({ limit: 100, ...filters }),
  });

  const getActionBadge = (action: string) => {
    switch (action) {
      case 'blocked': return <Badge variant="destructive">Blocked</Badge>;
      case 'guided': return <Badge variant="secondary">Guided</Badge>;
      default: return <Badge variant="outline">Passed</Badge>;
    }
  };

  if (isLoading) return <div>Loading...</div>;

  return (
    <div className="space-y-6">
      <h2 className="text-3xl font-bold">Conversations</h2>
      
      <div className="flex gap-4">
        <Select onValueChange={v => setFilters({...filters, action: v})}>
          <SelectTrigger className="w-40">
            <SelectValue placeholder="Filter by action" />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="">All</SelectItem>
            <SelectItem value="blocked">Blocked</SelectItem>
            <SelectItem value="guided">Guided</SelectItem>
            <SelectItem value="passed">Passed</SelectItem>
          </SelectContent>
        </Select>
      </div>

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Time</TableHead>
                <TableHead>Student</TableHead>
                <TableHead>Action</TableHead>
                <TableHead>Tokens</TableHead>
                <TableHead>Details</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data?.items.map((conv: Conversation) => (
                <TableRow key={conv.id}>
                  <TableCell>{new Date(conv.timestamp).toLocaleString()}</TableCell>
                  <TableCell className="font-mono text-xs">{conv.student_id.slice(0, 8)}...</TableCell>
                  <TableCell>{getActionBadge(conv.action_taken)}</TableCell>
                  <TableCell>{conv.tokens_used}</TableCell>
                  <TableCell>
                    <Dialog>
                      <DialogTrigger asChild>
                        <Button variant="ghost" size="sm">View</Button>
                      </DialogTrigger>
                      <DialogContent className="max-w-2xl">
                        <DialogHeader>
                          <DialogTitle>Conversation Details</DialogTitle>
                        </DialogHeader>
                        <div className="space-y-4">
                          <div>
                            <h4 className="font-semibold mb-1">Prompt:</h4>
                            <p className="text-sm bg-slate-100 p-2 rounded">{conv.prompt_text}</p>
                          </div>
                          <div>
                            <h4 className="font-semibold mb-1">Response:</h4>
                            <p className="text-sm bg-slate-100 p-2 rounded">{conv.response_text}</p>
                          </div>
                          {conv.rule_triggered && (
                            <div>
                              <h4 className="font-semibold mb-1">Rule Triggered:</h4>
                              <Badge>{conv.rule_triggered}</Badge>
                            </div>
                          )}
                        </div>
                      </DialogContent>
                    </Dialog>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
```

**Step 2: Create rules page**

```tsx
// web/src/pages/rules.tsx
import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { rulesApi } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Switch } from '@/components/ui/switch';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Plus, Trash2, RefreshCw } from 'lucide-react';
import type { Rule } from '@/types';

export function RulesPage() {
  const queryClient = useQueryClient();
  const [newRule, setNewRule] = useState({ pattern: '', rule_type: 'block', message: '', active_weeks: '1-16' });

  const { data: rules, isLoading } = useQuery({
    queryKey: ['rules'],
    queryFn: rulesApi.list,
  });

  const createMutation = useMutation({
    mutationFn: rulesApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['rules'] });
      setNewRule({ pattern: '', rule_type: 'block', message: '', active_weeks: '1-16' });
    },
  });

  const toggleMutation = useMutation({
    mutationFn: rulesApi.toggle,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['rules'] }),
  });

  const deleteMutation = useMutation({
    mutationFn: rulesApi.delete,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['rules'] }),
  });

  const reloadMutation = useMutation({
    mutationFn: rulesApi.reloadCache,
  });

  if (isLoading) return <div>Loading...</div>;

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <h2 className="text-3xl font-bold">Rules</h2>
        <Button variant="outline" onClick={() => reloadMutation.mutate()}>
          <RefreshCw className="mr-2 h-4 w-4" /> Reload Cache
        </Button>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Create New Rule</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label>Pattern (Regex)</Label>
              <Input 
                value={newRule.pattern}
                onChange={e => setNewRule({...newRule, pattern: e.target.value})}
                placeholder="e.g., .*write.*code.*"
              />
            </div>
            <div>
              <Label>Type</Label>
              <Select value={newRule.rule_type} onValueChange={v => setNewRule({...newRule, rule_type: v})}>
                <SelectTrigger><SelectValue /></SelectTrigger>
                <SelectContent>
                  <SelectItem value="block">Block</SelectItem>
                  <SelectItem value="guide">Guide</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>
          <div>
            <Label>Message</Label>
            <Textarea 
              value={newRule.message}
              onChange={e => setNewRule({...newRule, message: e.target.value})}
              placeholder="Message to return when rule matches..."
            />
          </div>
          <div>
            <Label>Active Weeks</Label>
            <Input 
              value={newRule.active_weeks}
              onChange={e => setNewRule({...newRule, active_weeks: e.target.value})}
              placeholder="e.g., 1-4, 8-12"
            />
          </div>
          <Button onClick={() => createMutation.mutate(newRule)}>Create Rule</Button>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Pattern</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Active Weeks</TableHead>
                <TableHead>Enabled</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rules?.map((rule: Rule) => (
                <TableRow key={rule.id}>
                  <TableCell className="font-mono text-xs max-w-xs truncate">{rule.pattern}</TableCell>
                  <TableCell>
                    <Badge variant={rule.rule_type === 'block' ? 'destructive' : 'secondary'}>
                      {rule.rule_type}
                    </Badge>
                  </TableCell>
                  <TableCell>{rule.active_weeks}</TableCell>
                  <TableCell>
                    <Switch 
                      checked={rule.enabled}
                      onCheckedChange={() => toggleMutation.mutate(rule.id)}
                    />
                  </TableCell>
                  <TableCell>
                    <Button variant="ghost" size="icon" onClick={() => deleteMutation.mutate(rule.id)}>
                      <Trash2 className="h-4 w-4 text-red-500" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
```

**Step 3: Create weekly prompts page**

```tsx
// web/src/pages/weekly-prompts.tsx
import { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { promptsApi } from '@/lib/api';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Switch } from '@/components/ui/switch';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Label } from '@/components/ui/label';
import { Plus, Trash2 } from 'lucide-react';
import type { WeeklyPrompt } from '@/types';

export function WeeklyPromptsPage() {
  const queryClient = useQueryClient();
  const [newPrompt, setNewPrompt] = useState({ 
    week_start: 1, 
    week_end: 4, 
    system_prompt: '', 
    description: '',
    is_active: true 
  });

  const { data: prompts, isLoading } = useQuery({
    queryKey: ['prompts'],
    queryFn: promptsApi.list,
  });

  const { data: currentPrompt } = useQuery({
    queryKey: ['prompts', 'current'],
    queryFn: promptsApi.getCurrent,
  });

  const createMutation = useMutation({
    mutationFn: promptsApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['prompts'] });
      setNewPrompt({ week_start: 1, week_end: 4, system_prompt: '', description: '', is_active: true });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: promptsApi.delete,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['prompts'] }),
  });

  if (isLoading) return <div>Loading...</div>;

  return (
    <div className="space-y-6">
      <h2 className="text-3xl font-bold">Weekly Prompts</h2>

      {currentPrompt && (
        <Card className="bg-blue-50 border-blue-200">
          <CardHeader>
            <CardTitle className="text-blue-800">Current Week Prompt</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-sm text-blue-600 mb-2">Weeks {currentPrompt.week_start}-{currentPrompt.week_end}</p>
            <p className="text-sm">{currentPrompt.system_prompt.slice(0, 200)}...</p>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Create New Prompt</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <Label>Week Start</Label>
              <Input 
                type="number" min={1} max={20}
                value={newPrompt.week_start}
                onChange={e => setNewPrompt({...newPrompt, week_start: parseInt(e.target.value)})}
              />
            </div>
            <div>
              <Label>Week End</Label>
              <Input 
                type="number" min={1} max={20}
                value={newPrompt.week_end}
                onChange={e => setNewPrompt({...newPrompt, week_end: parseInt(e.target.value)})}
              />
            </div>
          </div>
          <div>
            <Label>Description</Label>
            <Input 
              value={newPrompt.description}
              onChange={e => setNewPrompt({...newPrompt, description: e.target.value})}
              placeholder="e.g., Week 1-2: Introduction"
            />
          </div>
          <div>
            <Label>System Prompt</Label>
            <Textarea 
              value={newPrompt.system_prompt}
              onChange={e => setNewPrompt({...newPrompt, system_prompt: e.target.value})}
              placeholder="Enter system prompt..."
              rows={5}
            />
          </div>
          <div className="flex items-center gap-2">
            <Switch 
              checked={newPrompt.is_active}
              onCheckedChange={v => setNewPrompt({...newPrompt, is_active: v})}
            />
            <Label>Active</Label>
          </div>
          <Button onClick={() => createMutation.mutate(newPrompt)}>Create Prompt</Button>
        </CardContent>
      </Card>

      <Card>
        <CardContent className="p-0">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Weeks</TableHead>
                <TableHead>Description</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {prompts?.map((prompt: WeeklyPrompt) => (
                <TableRow key={prompt.id}>
                  <TableCell>Week {prompt.week_start}-{prompt.week_end}</TableCell>
                  <TableCell>{prompt.description || '-'}</TableCell>
                  <TableCell>
                    {prompt.is_active ? (
                      <Badge className="bg-green-500">Active</Badge>
                    ) : (
                      <Badge variant="secondary">Inactive</Badge>
                    )}
                  </TableCell>
                  <TableCell>
                    <Button variant="ghost" size="icon" onClick={() => deleteMutation.mutate(prompt.id)}>
                      <Trash2 className="h-4 w-4 text-red-500" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}
```

**Step 4: Fix missing import in rules.tsx**

Add to rules.tsx:
```tsx
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
```

**Step 5: Commit**

```bash
git add web/src/pages/conversations.tsx web/src/pages/rules.tsx web/src/pages/weekly-prompts.tsx
git commit -m "feat(web): add conversations, rules, and weekly prompts pages"
```

---

### Task 16: Build and Verify

**Step 1: Type check**

```bash
cd /Users/wangxq/Documents/python/web
npx tsc --noEmit
```

Expected: No errors

**Step 2: Build**

```bash
npm run build
```

Expected: Build succeeds, dist/ folder created

**Step 3: Final commit**

```bash
git add web/
git commit -m "feat(web): complete admin frontend with all pages"
```

---

## Summary

**Total Tasks: 16**
- Phase 1 (Backend): 6 tasks
- Phase 2 (Frontend): 10 tasks

**Key Features Delivered:**
- ✅ Complete REST API for admin operations
- ✅ Modern React + TypeScript + Vite frontend
- ✅ shadcn/ui components with Tailwind CSS
- ✅ TanStack Query for server state management
- ✅ Dashboard with statistics and charts
- ✅ Full CRUD for Students, Rules, Weekly Prompts
- ✅ Conversation browsing with filters
- ✅ Login with Admin Token
- ✅ Responsive layout with sidebar navigation

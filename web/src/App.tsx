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
    <BrowserRouter basename="/TeachProxy">
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

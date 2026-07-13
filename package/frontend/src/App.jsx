import React, { useEffect } from 'react';
import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import WelcomePage from './pages/WelcomePage';
import WorkspacePage from './pages/WorkspacePage';
import SessionDetailPage from './pages/SessionDetailPage';
import AdminDashboard from './pages/AdminDashboard';
import WordFormatterPage from './pages/WordFormatterPage';
import SpecGeneratorPage from './pages/SpecGeneratorPage';
import ArticlePreprocessorPage from './pages/ArticlePreprocessorPage';
import FormatCheckerPage from './pages/FormatCheckerPage';
import LegalPage from './pages/LegalPage';
import './index.css';

const ProtectedRoute = ({ children }) => {
  const cardKey = localStorage.getItem('cardKey');

  if (!cardKey) {
    return <Navigate to="/" replace />;
  }

  return children;
};

const MODULE_PATHS = [
  '/workspace',
  '/session/',
  '/word-formatter',
  '/spec-generator',
  '/article-preprocessor',
  '/format-checker',
];

const AppRoutes = () => {
  const location = useLocation();
  const isModuleRoute = MODULE_PATHS.some((path) => (
    path.endsWith('/') ? location.pathname.startsWith(path) : location.pathname === path
  ));

  useEffect(() => {
    if (isModuleRoute) {
      window.scrollTo({ top: 0, left: 0, behavior: 'auto' });
    }
  }, [location.pathname, isModuleRoute]);

  return (
    <div key={location.pathname} className={isModuleRoute ? 'module-page-enter' : undefined}>
      <Routes location={location}>
        <Route path="/" element={<WelcomePage />} />
        <Route path="/access/:cardKey" element={<WelcomePage />} />
        <Route path="/admin" element={<AdminDashboard />} />
        <Route path="/legal" element={<LegalPage />} />

        <Route
          path="/workspace"
          element={
            <ProtectedRoute>
              <WorkspacePage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/session/:sessionId"
          element={
            <ProtectedRoute>
              <SessionDetailPage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/word-formatter"
          element={
            <ProtectedRoute>
              <WordFormatterPage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/spec-generator"
          element={
            <ProtectedRoute>
              <SpecGeneratorPage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/article-preprocessor"
          element={
            <ProtectedRoute>
              <ArticlePreprocessorPage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/format-checker"
          element={
            <ProtectedRoute>
              <FormatCheckerPage />
            </ProtectedRoute>
          }
        />

        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </div>
  );
};

function App() {
  return (
    <BrowserRouter>
      <Toaster
        position="top-right"
        toastOptions={{
          duration: 3000,
          style: {
            background: '#ffffff',
            color: '#0f172a',
            border: '1px solid #e2e8f0',
            borderRadius: '8px',
            boxShadow: '0 12px 30px rgba(15, 23, 42, 0.12)',
          },
          success: {
            duration: 3000,
            iconTheme: {
              primary: '#10B981',
              secondary: '#fff',
            },
          },
          error: {
            duration: 4000,
            iconTheme: {
              primary: '#EF4444',
              secondary: '#fff',
            },
          },
        }}
      />

      <AppRoutes />
    </BrowserRouter>
  );
}

export default App;

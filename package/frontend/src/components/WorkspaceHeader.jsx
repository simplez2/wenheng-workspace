import React from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import {
  ChevronDown,
  FileCheck2,
  FileText,
  LayoutTemplate,
  ListChecks,
  LogOut,
  Wand2,
} from 'lucide-react';
import { APP_NAME } from '../branding';

export const WORKSPACE_MODULES = [
  { to: '/workspace', label: '文本优化', shortLabel: '文本优化', icon: Wand2 },
  { to: '/word-formatter', label: '文档排版', shortLabel: '文档排版', icon: FileText },
  { to: '/article-preprocessor', label: '内容预处理', shortLabel: '内容预处理', icon: ListChecks },
  { to: '/format-checker', label: '格式检查', shortLabel: '格式检查', icon: FileCheck2 },
  { to: '/spec-generator', label: '规范生成', shortLabel: '规范生成', icon: LayoutTemplate },
];

const resolveActiveModule = (pathname) => {
  if (pathname.startsWith('/session/')) {
    return WORKSPACE_MODULES[0];
  }
  return WORKSPACE_MODULES.find((item) => pathname === item.to) || WORKSPACE_MODULES[0];
};

const WorkspaceHeader = ({ rightContent = null }) => {
  const location = useLocation();
  const navigate = useNavigate();
  const activeModule = resolveActiveModule(location.pathname);
  const activeIndex = WORKSPACE_MODULES.findIndex((item) => item.to === activeModule.to);
  const ActiveIcon = activeModule.icon;

  const handleLogout = () => {
    localStorage.removeItem('cardKey');
    navigate('/');
  };

  return (
    <header className="sticky top-0 z-50 border-b border-slate-200 bg-white/95 backdrop-blur">
      <div className="mx-auto flex h-16 max-w-[1440px] items-center gap-5 px-4 sm:px-6 lg:px-8">
        <Link to="/workspace" className="flex min-w-max items-center gap-3" aria-label={`${APP_NAME}首页`}>
          <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-slate-950 text-white shadow-sm">
            <FileText className="h-5 w-5" />
          </div>
          <div>
            <p className="text-sm font-semibold leading-4 text-slate-950">{APP_NAME}</p>
            <p className="mt-1 hidden text-xs text-slate-400 sm:block">文稿处理空间</p>
          </div>
        </Link>

        <nav className="ml-3 hidden h-full min-w-0 flex-1 items-center gap-1 lg:flex" aria-label="功能模块">
          {WORKSPACE_MODULES.map((item) => {
            const Icon = item.icon;
            const isActive = item.to === activeModule.to;
            return (
              <Link
                key={item.to}
                to={item.to}
                aria-current={isActive ? 'page' : undefined}
                className={`relative inline-flex h-full min-w-0 items-center gap-2 border-b-2 px-3 text-sm font-medium transition-colors duration-150 ${
                  isActive
                    ? 'border-blue-600 bg-blue-50/70 text-blue-700'
                    : 'border-transparent text-slate-500 hover:bg-slate-50 hover:text-slate-950'
                }`}
              >
                <Icon className={`h-4 w-4 shrink-0 ${isActive ? 'text-blue-600' : ''}`} />
                <span className="truncate">{item.label}</span>
              </Link>
            );
          })}
        </nav>

        <div className="ml-auto flex min-w-0 items-center gap-2 sm:gap-3">
          {rightContent}
          <button
            type="button"
            onClick={handleLogout}
            className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md text-slate-500 transition-colors hover:bg-rose-50 hover:text-rose-600"
            title="退出登录"
            aria-label="退出登录"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>

      <div className="border-t border-slate-100 px-4 py-2.5 lg:hidden">
        <div className="mx-auto flex max-w-[1440px] items-center gap-3">
          <div className="flex min-w-0 flex-1 items-center gap-2.5">
            <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-blue-50 text-blue-600">
              <ActiveIcon className="h-4.5 w-4.5" />
            </div>
            <div className="min-w-0">
              <p className="text-[11px] font-medium text-slate-400">当前模块 {activeIndex + 1}/{WORKSPACE_MODULES.length}</p>
              <p className="truncate text-sm font-semibold text-slate-950">{activeModule.shortLabel}</p>
            </div>
          </div>

          <div className="relative shrink-0">
            <label className="sr-only" htmlFor="mobile-workspace-module">切换功能模块</label>
            <select
              id="mobile-workspace-module"
              value={activeModule.to}
              onChange={(event) => navigate(event.target.value)}
              className="h-10 appearance-none rounded-md border border-slate-200 bg-white py-0 pl-3 pr-9 text-sm font-medium text-slate-700 shadow-sm outline-none transition focus:border-blue-500"
            >
              {WORKSPACE_MODULES.map((item) => (
                <option key={item.to} value={item.to}>{item.label}</option>
              ))}
            </select>
            <ChevronDown className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          </div>
        </div>
      </div>
    </header>
  );
};

export default WorkspaceHeader;

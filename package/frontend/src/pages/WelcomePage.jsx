import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  ArrowRight,
  BookOpen,
  ClipboardCheck,
  FileText,
  History,
  KeyRound,
  LayoutTemplate,
  ListChecks,
  ShieldCheck,
  Sparkles,
} from 'lucide-react';
import axios from 'axios';
import toast from 'react-hot-toast';
import { healthAPI } from '../api';
import { APP_DESCRIPTION, APP_NAME, APP_TAGLINE } from '../branding';

const WORKSPACE_FEATURES = [
  { icon: Sparkles, title: '文本优化', description: '润色、增强与长文分段处理' },
  { icon: LayoutTemplate, title: '文档排版', description: 'Word 与 PDF 原格式处理' },
  { icon: ListChecks, title: '内容预处理', description: '结构整理与提交前检查' },
  { icon: ClipboardCheck, title: '格式检查', description: '逐项核对文档规范' },
  { icon: FileText, title: '规范生成', description: '保存并复用排版要求' },
  { icon: History, title: '任务管理', description: '批量队列、历史记录与继续处理' },
];

const WelcomePage = () => {
  const [cardKey, setCardKey] = useState('');
  const [loading, setLoading] = useState(false);
  const [apiStatus, setApiStatus] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    const checkApiHealth = async () => {
      try {
        const { data } = await healthAPI.checkModels();
        setApiStatus(data);
      } catch {
        setApiStatus(null);
      }
    };

    checkApiHealth();
  }, []);

  const serviceState = useMemo(() => {
    if (!apiStatus) {
      return { label: '正在连接', dot: 'bg-amber-500', text: 'text-amber-700' };
    }
    if (apiStatus.overall_status === 'healthy') {
      return { label: '服务正常', dot: 'bg-emerald-500', text: 'text-emerald-700' };
    }
    return { label: '部分能力受限', dot: 'bg-amber-500', text: 'text-amber-700' };
  }, [apiStatus]);

  const handleContinue = async () => {
    const normalizedKey = cardKey.trim();
    if (!normalizedKey) {
      toast.error('请输入访问码');
      return;
    }
    if (apiStatus?.overall_status === 'degraded') {
      const allUnavailable = Object.values(apiStatus.models || {}).every(
        (model) => model.status === 'unavailable',
      );
      if (allUnavailable) {
        toast.error('服务暂不可用，请稍后再试');
        return;
      }
    }

    setLoading(true);
    try {
      const { data } = await axios.post('/api/admin/verify-card-key', {
        card_key: normalizedKey,
      });
      if (data.valid) {
        localStorage.setItem('cardKey', normalizedKey);
        navigate('/workspace');
      }
    } catch (error) {
      toast.error(error.response?.data?.detail || '访问码无效或已停用');
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="min-h-screen bg-slate-50 text-slate-950">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-md bg-slate-950 text-white">
              <BookOpen className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm font-semibold leading-4">{APP_NAME}</p>
              <p className="mt-1 hidden text-xs text-slate-500 sm:block">{APP_TAGLINE}</p>
            </div>
          </div>

          <div className={`flex items-center gap-2 text-xs font-medium ${serviceState.text}`}>
            <span className={`h-2 w-2 rounded-full ${serviceState.dot}`} />
            {serviceState.label}
          </div>
        </div>
      </header>

      <div className="mx-auto grid min-h-[calc(100vh-64px)] max-w-6xl items-center gap-6 px-4 py-6 sm:gap-8 sm:px-6 sm:py-10 lg:grid-cols-[minmax(0,1fr)_400px] lg:gap-16 lg:py-14">
        <section className="max-w-2xl">
          <div className="inline-flex items-center gap-2 text-sm font-medium text-emerald-700">
            <ShieldCheck className="h-4 w-4" />
            私密文稿处理空间
          </div>
          <h1 className="mt-4 text-3xl font-semibold leading-tight sm:mt-5 sm:text-4xl">{APP_NAME}</h1>
          <p className="mt-3 text-base leading-7 text-slate-600 sm:mt-4">{APP_DESCRIPTION}</p>

          <div className="mt-6 grid grid-cols-2 border-y border-slate-200 sm:mt-9">
            {WORKSPACE_FEATURES.map(({ icon: Icon, title, description }, index) => (
              <div
                key={title}
                className={`flex min-h-[72px] items-center gap-2.5 py-2.5 sm:min-h-24 sm:gap-3.5 sm:py-4 ${
                  index % 2 === 0
                    ? 'pl-0 pr-2 sm:pr-4'
                    : 'border-l border-slate-200 pl-3 pr-0 sm:px-4'
                } ${index >= 2 ? 'border-t border-slate-200' : ''}`}
              >
                <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-white text-blue-700 shadow-sm ring-1 ring-slate-200 sm:h-10 sm:w-10">
                  <Icon className="h-4 w-4 sm:h-5 sm:w-5" />
                </div>
                <div className="min-w-0">
                  <h2 className="text-sm font-semibold text-slate-900">{title}</h2>
                  <p className="mt-1 hidden text-sm leading-5 text-slate-500 sm:block">{description}</p>
                </div>
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm sm:p-6 lg:p-7">
          <div className="flex h-11 w-11 items-center justify-center rounded-md bg-blue-50 text-blue-700">
            <KeyRound className="h-5 w-5" />
          </div>

          <h2 className="mt-5 text-xl font-semibold sm:mt-6">访问验证</h2>
          <p className="mt-1.5 text-sm leading-6 text-slate-600">输入访问码，继续处理已有任务或创建新任务。</p>

          <form
            className="mt-5 sm:mt-6"
            onSubmit={(event) => {
              event.preventDefault();
              handleContinue();
            }}
          >
            <label className="block text-sm font-medium text-slate-700" htmlFor="access-code">
              访问码
            </label>
            <input
              id="access-code"
              autoComplete="off"
              autoFocus
              value={cardKey}
              onChange={(event) => setCardKey(event.target.value)}
              placeholder="请输入访问码"
              className="mt-2 h-11 w-full rounded-md border border-slate-300 bg-white px-3 text-base outline-none transition placeholder:text-slate-400 focus:border-blue-600 focus:ring-2 focus:ring-blue-100"
            />

            <button
              type="submit"
              disabled={loading || !cardKey.trim()}
              className="mt-4 flex h-11 w-full items-center justify-center gap-2 rounded-md bg-blue-700 px-4 text-sm font-semibold text-white transition hover:bg-blue-800 disabled:cursor-not-allowed disabled:bg-slate-300 sm:mt-5"
            >
              {loading ? '正在验证...' : '验证并继续'}
              {!loading && <ArrowRight className="h-4 w-4" />}
            </button>
          </form>
        </section>
      </div>
    </main>
  );
};

export default WelcomePage;

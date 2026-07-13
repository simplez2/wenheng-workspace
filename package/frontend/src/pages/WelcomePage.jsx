import React, { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  AlertTriangle,
  ArrowRight,
  BookOpen,
  KeyRound,
  ShieldCheck,
} from 'lucide-react';
import axios from 'axios';
import toast from 'react-hot-toast';
import { healthAPI } from '../api';
import { APP_DESCRIPTION, APP_NAME, APP_TAGLINE, LEGAL_PATH } from '../branding';

const WelcomePage = () => {
  const [cardKey, setCardKey] = useState('');
  const [showNotice, setShowNotice] = useState(false);
  const [acceptedNotice, setAcceptedNotice] = useState(false);
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
    if (!acceptedNotice) {
      toast.error('请先阅读并确认使用说明');
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
        <div className="mx-auto flex h-16 max-w-5xl items-center justify-between px-4 sm:px-6">
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

      <div className="mx-auto grid min-h-[calc(100vh-64px)] max-w-5xl items-center gap-8 px-4 py-8 sm:px-6 lg:grid-cols-[minmax(0,1fr)_420px] lg:gap-14">
        <section className="max-w-xl">
          <div className="inline-flex items-center gap-2 rounded-md border border-emerald-200 bg-emerald-50 px-3 py-1.5 text-xs font-semibold text-emerald-800">
            <ShieldCheck className="h-4 w-4" />
            私密文稿处理空间
          </div>
          <h1 className="mt-5 text-3xl font-semibold leading-tight sm:text-4xl">{APP_NAME}</h1>
          <p className="mt-4 text-base leading-7 text-slate-600">{APP_DESCRIPTION}</p>

          <div className="mt-8 border-l-2 border-slate-300 pl-4 text-sm leading-6 text-slate-500">
            访问码由管理员分配。进入后可继续上次任务，并查看已保存的处理记录。
          </div>
        </section>

        <section className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm sm:p-6">
          <div className="flex items-start justify-between gap-4">
            <div className="flex h-10 w-10 items-center justify-center rounded-md bg-slate-100 text-slate-900">
              <KeyRound className="h-5 w-5" />
            </div>
            <span className="text-xs font-medium text-slate-400">安全访问</span>
          </div>

          <h2 className="mt-5 text-xl font-semibold">进入工作台</h2>
          <p className="mt-1.5 text-sm leading-6 text-slate-600">输入管理员分配的访问码。</p>

          <form
            className="mt-6"
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

            <div className="mt-4 rounded-md border border-slate-200 bg-slate-50">
              <div className="flex items-center justify-between gap-3 px-3 py-2.5">
                <label className="flex min-w-0 items-center gap-2.5 text-sm text-slate-700">
                  <input
                    type="checkbox"
                    checked={acceptedNotice}
                    onChange={(event) => setAcceptedNotice(event.target.checked)}
                    className="h-4 w-4 rounded border-slate-300 text-blue-600 focus:ring-blue-500"
                  />
                  <span>我已阅读并理解使用说明</span>
                </label>
                <button
                  type="button"
                  onClick={() => setShowNotice((current) => !current)}
                  className="shrink-0 text-xs font-medium text-blue-600 hover:underline"
                >
                  {showNotice ? '收起' : '查看'}
                </button>
              </div>

              {showNotice && (
                <div className="border-t border-slate-200 px-3 py-3 text-xs leading-5 text-slate-600">
                  <div className="flex gap-2">
                    <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-amber-600" />
                    <p>
                      本服务用于语言表达、结构整理和文档处理，不替代独立研究与学术判断。请核对处理结果，并遵守所在机构的相关规定。
                    </p>
                  </div>
                </div>
              )}
            </div>

            <button
              type="submit"
              disabled={loading || !cardKey.trim() || !acceptedNotice}
              className="mt-4 flex h-11 w-full items-center justify-center gap-2 rounded-md bg-slate-950 px-4 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300"
            >
              {loading ? '正在验证...' : '进入工作台'}
              {!loading && <ArrowRight className="h-4 w-4" />}
            </button>
          </form>

          <div className="mt-5 flex items-center justify-between border-t border-slate-100 pt-4 text-xs text-slate-500">
            <span>访问码仅用于身份验证</span>
            <Link to={LEGAL_PATH} className="font-medium hover:text-slate-900 hover:underline">
              开源许可
            </Link>
          </div>
        </section>
      </div>
    </main>
  );
};

export default WelcomePage;

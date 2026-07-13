import React, { useState, useEffect, useCallback, useMemo, useRef, memo } from 'react';
import { useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import {
  Activity,
  AlertCircle,
  BookOpen,
  CheckCircle2,
  Clock,
  FileText,
  History,
  Layers3,
  Play,
  RefreshCw,
  Sparkles,
  Trash2,
  Upload,
  X,
  Users,
} from 'lucide-react';
import { optimizationAPI } from '../api';
import WorkspaceHeader from '../components/WorkspaceHeader';

const PROCESSING_MODES = [
  {
    id: 'paper_polish',
    title: '语言润色',
    desc: '改善语句、逻辑与学术表达',
    detail: '改善语句通顺度、逻辑衔接与学术表达。',
    icon: FileText,
  },
  {
    id: 'paper_enhance',
    title: '表达优化',
    desc: '重组句式并提升表述清晰度',
    detail: '在已有文本基础上进行表达重写与结构优化。',
    icon: Sparkles,
  },
  {
    id: 'paper_polish_enhance',
    title: '完整优化',
    desc: '依次完成语言与表达处理',
    detail: '依次完成语言润色与表达优化，适合需要完整处理的内容。',
    icon: Layers3,
  },
  {
    id: 'emotion_polish',
    title: '自然表达',
    desc: '生成更流畅、易读的文本',
    detail: '将文本调整为更自然、易读的表达方式。',
    icon: BookOpen,
  },
];

const SOURCE_FILE_EXTENSIONS = new Set(['docx', 'pdf', 'txt', 'md']);
const MAX_SOURCE_FILE_SIZE = 25 * 1024 * 1024;

const getFileExtension = (filename) => filename.split('.').pop()?.toLowerCase() || '';

const getStatusMeta = (status) => {
  const states = {
    completed: { label: '已完成', icon: CheckCircle2, tone: 'text-emerald-700', bg: 'bg-emerald-50' },
    processing: { label: '处理中', icon: Activity, tone: 'text-sky-700', bg: 'bg-sky-50' },
    queued: { label: '排队中', icon: Clock, tone: 'text-amber-700', bg: 'bg-amber-50' },
    failed: { label: '失败', icon: AlertCircle, tone: 'text-rose-700', bg: 'bg-rose-50' },
    stopped: { label: '已停止', icon: AlertCircle, tone: 'text-slate-600', bg: 'bg-slate-100' },
  };
  return states[status] || { label: status, icon: Clock, tone: 'text-slate-600', bg: 'bg-slate-100' };
};

const SessionItem = memo(({ session, activeSession, onView, onDelete, onRetry }) => {
  const statusMeta = getStatusMeta(session.status);
  const StatusIcon = statusMeta.icon;
  const isActive = activeSession === session.session_id;

  const handleDelete = useCallback((event) => {
    event.stopPropagation();
    onDelete(session);
  }, [session, onDelete]);

  const handleRetry = useCallback((event) => {
    event.stopPropagation();
    if (session.status === 'failed' || session.status === 'stopped') {
      onRetry(session);
    }
  }, [session, onRetry]);

  const handleView = useCallback(() => {
    onView(session.session_id);
  }, [session.session_id, onView]);

  return (
    <article className={`rounded-lg border transition ${isActive ? 'border-sky-200 bg-sky-50/60' : 'border-slate-200 bg-white hover:border-slate-300'}`}>
      <button
        type="button"
        onClick={handleView}
        className="w-full px-3.5 pb-2 pt-3.5 text-left"
      >
        <div className="flex items-center justify-between gap-3">
          <span className={`inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs font-semibold ${statusMeta.bg} ${statusMeta.tone}`}>
            <StatusIcon className={`h-3.5 w-3.5 ${session.status === 'processing' ? 'animate-pulse' : ''}`} />
            {statusMeta.label}
          </span>
          <time className="text-xs text-slate-400">
            {new Date(session.created_at).toLocaleDateString('zh-CN', { month: '2-digit', day: '2-digit' })}
          </time>
        </div>

        <p className="mt-2.5 line-clamp-2 min-h-[40px] text-sm leading-5 text-slate-700">
          {session.preview_text || '暂无预览'}
        </p>

        {session.status === 'processing' && (
          <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-slate-100">
            <div
              className="h-full rounded-full bg-sky-500 transition-all duration-500"
              style={{ width: `${session.progress}%` }}
            />
          </div>
        )}
      </button>

      <div className="flex min-h-10 items-center justify-between border-t border-slate-100 px-3.5 py-1.5">
        {(session.status === 'failed' || session.status === 'stopped') ? (
          <button
            type="button"
            onClick={handleRetry}
            className="inline-flex items-center gap-1.5 rounded-md px-2 py-1.5 text-xs font-semibold text-amber-700 transition hover:bg-amber-50"
          >
            <RefreshCw className="h-3.5 w-3.5" />
            {session.status === 'stopped' ? '继续处理' : '重新处理'}
          </button>
        ) : (
          <span className="text-xs text-slate-400">
            {session.total_segments ? `${session.total_segments} 个段落` : '查看详情'}
          </span>
        )}
        <button
          type="button"
          onClick={handleDelete}
          className="rounded-md p-2 text-slate-400 transition hover:bg-rose-50 hover:text-rose-600"
          title="删除会话"
          aria-label="删除会话"
        >
          <Trash2 className="h-4 w-4" />
        </button>
      </div>

      {(session.status === 'failed' || session.status === 'stopped') && session.current_position < session.total_segments && (
        <p className={`border-t px-3.5 py-2 text-xs ${session.status === 'stopped' ? 'border-amber-100 bg-amber-50 text-amber-700' : 'border-rose-100 bg-rose-50 text-rose-700'}`}>
          {session.status === 'stopped' ? '任务已暂停，可从未完成段落继续。' : (session.error_message ? '处理过程中发生错误' : '网络连接超时')}
        </p>
      )}
    </article>
  );
});

SessionItem.displayName = 'SessionItem';

const WorkspacePage = () => {
  const [text, setText] = useState('');
  const [sourceFile, setSourceFile] = useState(null);
  const [isDraggingFile, setIsDraggingFile] = useState(false);
  const [processingMode, setProcessingMode] = useState('paper_polish_enhance');
  const [sessions, setSessions] = useState([]);
  const [queueStatus, setQueueStatus] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isLoadingSessions, setIsLoadingSessions] = useState(false);
  const [showMobileHistory, setShowMobileHistory] = useState(false);
  const fileInputRef = useRef(null);
  const dragDepthRef = useRef(0);
  const navigate = useNavigate();

  const selectSourceFile = useCallback((file) => {
    if (!file) return;

    if (!SOURCE_FILE_EXTENSIONS.has(getFileExtension(file.name))) {
      toast.error('仅支持 DOCX、PDF、TXT、MD 文件');
      return;
    }

    if (file.size > MAX_SOURCE_FILE_SIZE) {
      toast.error('文件不能超过 25 MB');
      return;
    }

    if (file.size === 0) {
      toast.error('不能导入空文件');
      return;
    }

    setSourceFile(file);
    setText('');
  }, []);

  const handleFileDragEnter = useCallback((event) => {
    event.preventDefault();
    event.stopPropagation();
    dragDepthRef.current += 1;
    setIsDraggingFile(true);
  }, []);

  const handleFileDragLeave = useCallback((event) => {
    event.preventDefault();
    event.stopPropagation();
    dragDepthRef.current = Math.max(0, dragDepthRef.current - 1);
    if (dragDepthRef.current === 0) setIsDraggingFile(false);
  }, []);

  const handleFileDrop = useCallback((event) => {
    event.preventDefault();
    event.stopPropagation();
    dragDepthRef.current = 0;
    setIsDraggingFile(false);

    const files = event.dataTransfer.files;
    if (files.length > 1) {
      toast.error('每次只能导入一个文件');
      return;
    }
    selectSourceFile(files[0]);
  }, [selectSourceFile]);

  const loadSessions = useCallback(async () => {
    try {
      setIsLoadingSessions(true);
      const response = await optimizationAPI.listSessions();
      setSessions(response.data);

    } catch (error) {
      console.error('加载会话失败:', error);
    } finally {
      setIsLoadingSessions(false);
    }
  }, []);

  const loadQueueStatus = useCallback(async () => {
    try {
      const response = await optimizationAPI.getQueueStatus();
      setQueueStatus(response.data);
    } catch (error) {
      console.error('加载队列状态失败:', error);
    }
  }, []);

  const updateSessionProgress = useCallback(async (sessionId) => {
    try {
      const response = await optimizationAPI.getSessionProgress(sessionId);
      const progress = response.data;

      setSessions((previousSessions) => {
        const target = previousSessions.find((session) => session.session_id === sessionId);
        if (target && target.progress === progress.progress && target.status === progress.status) {
          return previousSessions;
        }
        return previousSessions.map((session) => (
          session.session_id === sessionId ? { ...session, ...progress } : session
        ));
      });

      if (progress.status === 'completed' || progress.status === 'failed' || progress.status === 'stopped') {
        loadSessions();
        loadQueueStatus();

        if (progress.status === 'completed') {
          toast.success('优化完成');
        } else {
          toast.error(`优化失败: ${progress.error_message}`);
        }
      }
    } catch (error) {
      console.error('更新进度失败:', error);
    }
  }, [loadSessions, loadQueueStatus]);

  useEffect(() => {
    loadSessions();
    loadQueueStatus();
  }, [loadSessions, loadQueueStatus]);

  useEffect(() => {
    const interval = setInterval(loadQueueStatus, 15000);
    return () => clearInterval(interval);
  }, [loadQueueStatus]);

  useEffect(() => {
    const activeSessionIds = sessions
      .filter((session) => session.status === 'processing' || session.status === 'queued')
      .map((session) => session.session_id);
    if (activeSessionIds.length > 0) {
      const interval = setInterval(() => {
        activeSessionIds.forEach(updateSessionProgress);
      }, 4000);
      return () => clearInterval(interval);
    }
    return undefined;
  }, [sessions, updateSessionProgress]);

  const handleStartOptimization = useCallback(async () => {
    if (!text.trim() && !sourceFile) {
      toast.error('请输入文本或选择要优化的文件');
      return;
    }

    if (isSubmitting) {
      return;
    }

    try {
      setIsSubmitting(true);
      const response = sourceFile
        ? await optimizationAPI.startFileOptimization(sourceFile, processingMode)
        : await optimizationAPI.startOptimization({
            original_text: text,
            processing_mode: processingMode,
          });

      toast.success('优化任务已启动');
      setText('');
      setSourceFile(null);
      loadSessions();
      loadQueueStatus();
    } catch (error) {
      toast.error('启动优化失败: ' + error.response?.data?.detail);
    } finally {
      setIsSubmitting(false);
    }
  }, [text, sourceFile, processingMode, isSubmitting, loadSessions, loadQueueStatus]);

  const handleDeleteSession = useCallback(async (session) => {
    const confirmDelete = window.confirm('确认删除该会话及其结果吗?');
    if (!confirmDelete) {
      return;
    }

    try {
      await optimizationAPI.deleteSession(session.session_id);
      toast.success('会话已删除');
      await loadSessions();
      await loadQueueStatus();
    } catch (error) {
      console.error('删除会话失败:', error);
      toast.error(error.response?.data?.detail || '删除会话失败');
    }
  }, [loadSessions, loadQueueStatus]);

  const handleViewSession = useCallback((sessionId) => {
    navigate(`/session/${sessionId}`);
  }, [navigate]);

  const handleRetrySegment = useCallback(async (session) => {
    if (!['failed', 'stopped'].includes(session.status)) {
      return;
    }

    const confirmRetry = window.confirm(
      session.status === 'stopped'
        ? '继续处理尚未完成的段落吗？已完成内容不会重复处理。'
        : '检测到会话执行失败。是否重新处理未完成的段落？',
    );
    if (!confirmRetry) {
      return;
    }

    try {
      const response = await optimizationAPI.resumeSession(session.session_id);
      toast.success(response.data?.message || '已重新继续处理未完成段落');
      await loadSessions();
    } catch (error) {
      console.error('重试失败:', error);
      toast.error(error.response?.data?.detail || '重试失败，请稍后再试');
    }
  }, [loadSessions]);

  const activeSessions = useMemo(() => (
    sessions.filter((session) => session.status === 'processing' || session.status === 'queued')
  ), [sessions]);
  const activeSession = activeSessions[0]?.session_id || null;
  const currentActiveSessionData = activeSessions[0] || null;
  const canSubmit = queueStatus?.can_submit ?? activeSessions.length === 0;

  const selectedMode = useMemo(() => (
    PROCESSING_MODES.find((mode) => mode.id === processingMode) || PROCESSING_MODES[0]
  ), [processingMode]);

  return (
    <div className="min-h-screen bg-[#f4f6f7] text-slate-950">
      <WorkspaceHeader
        rightContent={queueStatus && (
          <div className="hidden items-center gap-2 sm:flex">
            <span className="inline-flex items-center gap-1.5 rounded-md bg-slate-100 px-2.5 py-1.5 text-xs font-medium text-slate-600" title="全局任务并发">
              <Users className="h-3.5 w-3.5" />
              全局 {queueStatus.current_users}/{queueStatus.max_users}
            </span>
            {queueStatus.queue_length > 0 && (
              <span className="inline-flex items-center gap-1.5 rounded-md bg-amber-50 px-2.5 py-1.5 text-xs font-medium text-amber-700">
                <Clock className="h-3.5 w-3.5" />
                {queueStatus.queue_length} 排队
              </span>
            )}
          </div>
        )}
      />

      <main className="mx-auto max-w-[1440px] px-4 py-4 sm:px-6 lg:px-8 lg:py-6">
        <div className="mb-4 flex items-center justify-between gap-3">
          <div className="min-w-0">
            <h1 className="text-xl font-semibold text-slate-950">文本优化</h1>
            <p className="mt-1 hidden truncate text-sm text-slate-500 sm:block">{selectedMode.detail}</p>
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <button
              type="button"
              onClick={() => setShowMobileHistory((current) => !current)}
              className="inline-flex h-9 items-center gap-2 rounded-md border border-slate-200 bg-white px-3 text-sm font-medium text-slate-700 xl:hidden"
            >
              <History className="h-4 w-4" />
              历史 {sessions.length}
            </button>
            <div className="hidden items-center gap-2 text-xs text-slate-500 sm:flex">
              <span className={`h-2 w-2 rounded-full ${activeSession ? 'bg-amber-500' : 'bg-emerald-500'}`} />
              {activeSessions.length > 0
                ? `我的任务 ${activeSessions.length}/${queueStatus?.user_task_limit || 1}`
                : '可提交任务'}
            </div>
          </div>
        </div>

        {showMobileHistory && (
          <section className="mb-4 overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm xl:hidden">
            <div className="flex h-12 items-center justify-between border-b border-slate-200 px-4">
              <div className="flex items-center gap-2">
                <History className="h-4 w-4 text-slate-400" />
                <h2 className="text-sm font-semibold">历史记录</h2>
              </div>
              <span className="text-xs text-slate-500">{sessions.length} 条</span>
            </div>
            <div className="max-h-72 space-y-2 overflow-y-auto p-3">
              {isLoadingSessions ? (
                <div className="flex items-center justify-center py-10">
                  <RefreshCw className="h-5 w-5 animate-spin text-slate-400" />
                </div>
              ) : sessions.length === 0 ? (
                <p className="py-10 text-center text-sm text-slate-500">暂无处理记录</p>
              ) : (
                sessions.map((session) => (
                  <SessionItem
                    key={session.id}
                    session={session}
                    activeSession={activeSession}
                    onView={handleViewSession}
                    onDelete={handleDeleteSession}
                    onRetry={handleRetrySegment}
                  />
                ))
              )}
            </div>
          </section>
        )}

        <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
          <div className="space-y-4">
            <section className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
              <div className="flex items-center justify-between gap-3 border-b border-slate-200 px-4 py-3.5">
                <h2 className="text-base font-semibold">新建处理任务</h2>
                <span className="inline-flex shrink-0 items-center gap-1.5 rounded bg-emerald-50 px-2 py-1 text-xs font-semibold text-emerald-700">
                  <Activity className="h-3.5 w-3.5" />
                  {activeSessions.length > 0
                    ? `并发 ${activeSessions.length}/${queueStatus?.user_task_limit || 1}`
                    : '可提交'}
                </span>
              </div>

              <div className="p-4">
                <fieldset>
                  <legend className="text-xs font-semibold text-slate-500">处理模式</legend>
                  <div className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-4" role="radiogroup" aria-label="处理模式">
                    {PROCESSING_MODES.map((mode) => {
                      const ModeIcon = mode.icon;
                      const selected = processingMode === mode.id;
                      return (
                        <label
                          key={mode.id}
                          className={`flex min-h-[52px] cursor-pointer items-center gap-2 rounded-md border px-3 py-2.5 transition ${
                            selected
                              ? 'border-emerald-500 bg-emerald-50/70 ring-1 ring-emerald-500/20'
                              : 'border-slate-200 bg-white hover:border-slate-300 hover:bg-slate-50'
                          }`}
                        >
                          <input
                            type="radio"
                            name="processingMode"
                            value={mode.id}
                            checked={selected}
                            onChange={(event) => setProcessingMode(event.target.value)}
                            className="sr-only"
                          />
                          <ModeIcon className={`h-4 w-4 shrink-0 ${selected ? 'text-emerald-700' : 'text-slate-400'}`} />
                          <p className={`min-w-0 flex-1 truncate text-sm font-semibold ${selected ? 'text-emerald-900' : 'text-slate-900'}`}>
                            {mode.title}
                          </p>
                          <span className={`h-3 w-3 shrink-0 rounded-full border ${selected ? 'border-emerald-600 bg-emerald-600 ring-2 ring-emerald-100' : 'border-slate-300'}`} />
                          <span className="sr-only">{mode.desc}</span>
                        </label>
                      );
                    })}
                  </div>
                </fieldset>

                <p className="mt-2 text-xs leading-5 text-slate-500">{selectedMode.detail}</p>

                <div
                  role="button"
                  tabIndex={0}
                  aria-label={sourceFile ? '更换导入文件' : '导入文档'}
                  onClick={() => fileInputRef.current?.click()}
                  onKeyDown={(event) => {
                    if (event.key === 'Enter' || event.key === ' ') {
                      event.preventDefault();
                      fileInputRef.current?.click();
                    }
                  }}
                  onDragEnter={handleFileDragEnter}
                  onDragOver={(event) => {
                    event.preventDefault();
                    event.stopPropagation();
                    event.dataTransfer.dropEffect = 'copy';
                  }}
                  onDragLeave={handleFileDragLeave}
                  onDrop={handleFileDrop}
                  className={`mt-3 flex cursor-pointer flex-col gap-3 rounded-md border border-dashed p-3 transition sm:flex-row sm:items-center sm:justify-between ${
                    isDraggingFile
                      ? 'border-emerald-500 bg-emerald-50 ring-2 ring-emerald-500/20'
                      : 'border-slate-300 bg-slate-50 hover:border-emerald-400 hover:bg-emerald-50/40'
                  }`}
                >
                  <div className="min-w-0">
                    {isDraggingFile ? (
                      <>
                        <p className="text-sm font-semibold text-emerald-800">松开即可导入文件</p>
                        <p className="mt-0.5 text-xs text-emerald-700">每次支持导入一个文档</p>
                      </>
                    ) : sourceFile ? (
                      <>
                        <p className="truncate text-sm font-semibold text-slate-800">{sourceFile.name}</p>
                        <p className="mt-0.5 text-xs text-slate-500">
                          {(sourceFile.size / 1024 / 1024).toFixed(2)} MB · 完成后默认按原格式导出
                        </p>
                      </>
                    ) : (
                      <>
                        <p className="text-sm font-semibold text-slate-700">导入文档并保留原格式</p>
                        <p className="mt-0.5 text-xs text-slate-500">拖放文件到这里，或点击选择 · DOCX、PDF、TXT、MD · 最大 25 MB</p>
                      </>
                    )}
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    {sourceFile && (
                      <button
                        type="button"
                        onClick={(event) => {
                          event.stopPropagation();
                          setSourceFile(null);
                        }}
                        className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-500 hover:text-rose-600"
                        title="移除文件"
                      >
                        <X className="h-4 w-4" />
                      </button>
                    )}
                    <span className={`inline-flex h-9 items-center gap-2 rounded-md border bg-white px-3 text-sm font-semibold ${isDraggingFile ? 'border-emerald-300 text-emerald-700' : 'border-slate-300 text-slate-700'}`}>
                      <Upload className="h-4 w-4" />
                      {isDraggingFile ? '放置文件' : sourceFile ? '更换文件' : '选择文件'}
                    </span>
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept=".docx,.pdf,.txt,.md,text/plain,text/markdown,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                      className="sr-only"
                      onChange={(event) => {
                        selectSourceFile(event.target.files?.[0]);
                        event.target.value = '';
                      }}
                    />
                  </div>
                </div>

                <div className="mt-3 overflow-hidden rounded-md border border-slate-300 bg-white focus-within:border-emerald-600 focus-within:ring-2 focus-within:ring-emerald-600/10">
                  <textarea
                    value={text}
                    onChange={(event) => {
                      setText(event.target.value);
                      if (event.target.value) setSourceFile(null);
                    }}
                    disabled={Boolean(sourceFile)}
                    placeholder={sourceFile ? '已选择文档，将从文件中读取文字' : '在此粘贴需要处理的内容...'}
                    className="min-h-[220px] w-full resize-y bg-transparent px-4 py-3.5 text-base leading-7 text-slate-900 outline-none placeholder:text-slate-400 sm:min-h-[300px] lg:min-h-[340px]"
                  />
                  <div className="flex flex-col gap-2 border-t border-slate-200 bg-slate-50 px-3 py-2.5 sm:flex-row sm:items-center sm:justify-between">
                    <div className="flex items-center gap-3 text-xs text-slate-500">
                      <span>{sourceFile ? '文件模式' : `${text.length.toLocaleString()} 字`}</span>
                      {!canSubmit && (
                        <span className="text-amber-700">
                          已达到账号并发上限 {queueStatus?.user_task_limit || 1}
                        </span>
                      )}
                    </div>
                    <button
                      type="button"
                      onClick={handleStartOptimization}
                      disabled={(!text.trim() && !sourceFile) || !canSubmit || isSubmitting}
                      className="inline-flex h-10 w-full items-center justify-center gap-2 rounded-md bg-slate-950 px-5 text-sm font-semibold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:bg-slate-300 sm:w-auto"
                    >
                      {isSubmitting ? (
                        <>
                          <RefreshCw className="h-4 w-4 animate-spin" />
                          正在提交
                        </>
                      ) : (
                        <>
                          <Play className="h-4 w-4 fill-current" />
                          开始优化
                        </>
                      )}
                    </button>
                  </div>
                </div>
              </div>
            </section>

            {activeSession && currentActiveSessionData && (
              <section className="rounded-lg border border-sky-200 bg-white p-4 shadow-[0_8px_24px_rgba(15,23,42,0.04)] sm:p-5">
                <div className="flex items-center justify-between gap-4">
                  <div className="flex items-center gap-2.5">
                    <span className="h-2.5 w-2.5 animate-pulse rounded-full bg-sky-500" />
                    <div>
                      <h2 className="text-sm font-semibold text-slate-900">任务处理中</h2>
                      <p className="mt-0.5 text-xs text-slate-500">
                        {currentActiveSessionData.current_stage === 'enhance' ? '表达优化' : currentActiveSessionData.current_stage === 'emotion_polish' ? '自然表达' : '语言润色'}
                      </p>
                    </div>
                  </div>
                  <span className="text-sm font-semibold text-sky-700">
                    {Number(currentActiveSessionData.progress || 0).toFixed(1)}%
                  </span>
                </div>
                <div className="mt-4 h-2 overflow-hidden rounded-full bg-slate-100">
                  <div
                    className="h-full rounded-full bg-sky-500 transition-all duration-500"
                    style={{ width: `${currentActiveSessionData.progress}%` }}
                  />
                </div>
                <div className="mt-3 flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
                  <span>
                    进度 {currentActiveSessionData.current_position + 1} / {currentActiveSessionData.total_segments} 段
                  </span>
                  {currentActiveSessionData.status === 'queued' && queueStatus?.your_position && (
                    <span className="text-amber-700">
                      排队第 {queueStatus.your_position} 位，约 {Math.ceil(queueStatus.estimated_wait_time / 60)} 分钟
                    </span>
                  )}
                </div>
              </section>
            )}
          </div>

          <aside className="hidden xl:block xl:sticky xl:top-20 xl:self-start">
            <section className="flex max-h-[calc(100vh-104px)] min-h-[420px] flex-col overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
              <div className="flex min-h-16 items-center justify-between border-b border-slate-200 px-4">
                <div className="flex items-center gap-2.5">
                  <History className="h-4.5 w-4.5 text-slate-400" />
                  <h2 className="text-sm font-semibold">历史记录</h2>
                </div>
                <span className="rounded-md bg-slate-100 px-2 py-1 text-xs font-medium text-slate-500">
                  {sessions.length}
                </span>
              </div>

              <div className="flex-1 space-y-2 overflow-y-auto p-3">
                {isLoadingSessions ? (
                  <div className="flex items-center justify-center py-16">
                    <RefreshCw className="h-5 w-5 animate-spin text-slate-400" />
                  </div>
                ) : sessions.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-16 text-center">
                    <div className="flex h-11 w-11 items-center justify-center rounded-lg bg-slate-100 text-slate-400">
                      <History className="h-5 w-5" />
                    </div>
                    <p className="mt-3 text-sm font-medium text-slate-600">暂无处理记录</p>
                    <p className="mt-1 text-xs text-slate-400">完成的任务会显示在这里</p>
                  </div>
                ) : (
                  sessions.map((session) => (
                    <SessionItem
                      key={session.id}
                      session={session}
                      activeSession={activeSession}
                      onView={handleViewSession}
                      onDelete={handleDeleteSession}
                      onRetry={handleRetrySegment}
                    />
                  ))
                )}
              </div>
            </section>
          </aside>
        </div>
      </main>
    </div>
  );
};

export default WorkspacePage;

import React, { useState, useEffect, useCallback, useMemo, useRef, memo } from 'react';
import { useNavigate } from 'react-router-dom';
import toast from 'react-hot-toast';
import {
  Activity,
  AlertCircle,
  BookOpen,
  CheckCircle2,
  Clock,
  Download,
  FileArchive,
  FileText,
  Files,
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
const MAX_BATCH_FILES = 20;

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

        {session.source_filename && (
          <p className="mt-2.5 flex items-center gap-1.5 truncate text-sm font-semibold text-slate-800">
            <FileText className="h-3.5 w-3.5 shrink-0 text-slate-400" />
            <span className="truncate">{session.source_filename}</span>
          </p>
        )}
        <p className={`${session.source_filename ? 'mt-1' : 'mt-2.5'} line-clamp-2 min-h-[40px] text-sm leading-5 text-slate-600`}>
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
  const [sourceFiles, setSourceFiles] = useState([]);
  const [isDraggingFile, setIsDraggingFile] = useState(false);
  const [processingMode, setProcessingMode] = useState('paper_polish_enhance');
  const [sessions, setSessions] = useState([]);
  const [queueStatus, setQueueStatus] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isLoadingSessions, setIsLoadingSessions] = useState(false);
  const [exportingBatchId, setExportingBatchId] = useState(null);
  const [showMobileHistory, setShowMobileHistory] = useState(false);
  const fileInputRef = useRef(null);
  const dragDepthRef = useRef(0);
  const navigate = useNavigate();

  const selectSourceFiles = useCallback((fileList) => {
    const incoming = Array.from(fileList || []);
    if (incoming.length === 0) return;
    const maxFileSize = (queueStatus?.max_upload_file_size_mb || 20) * 1024 * 1024;
    const maxBatchFiles = queueStatus?.max_batch_files || MAX_BATCH_FILES;
    const maxBatchTotalSize = (queueStatus?.max_batch_total_size_mb || 100) * 1024 * 1024;

    const valid = [];
    let invalidCount = 0;
    incoming.forEach((file) => {
      if (!SOURCE_FILE_EXTENSIONS.has(getFileExtension(file.name)) || file.size === 0 || file.size > maxFileSize) {
        invalidCount += 1;
        return;
      }
      valid.push(file);
    });
    if (invalidCount > 0) {
      toast.error(`${invalidCount} 个文件不符合格式、大小或非空要求`);
    }

    const existingKeys = new Set(sourceFiles.map((file) => `${file.name}:${file.size}:${file.lastModified}`));
    const merged = [...sourceFiles];
    valid.forEach((file) => {
      const key = `${file.name}:${file.size}:${file.lastModified}`;
      if (!existingKeys.has(key)) {
        existingKeys.add(key);
        merged.push(file);
      }
    });
    if (merged.length > maxBatchFiles) {
      toast.error(`每批最多选择 ${maxBatchFiles} 个文件`);
      return;
    }
    if (merged.reduce((sum, file) => sum + file.size, 0) > maxBatchTotalSize) {
      toast.error(`单批文件总大小不能超过 ${queueStatus?.max_batch_total_size_mb || 100} MB`);
      return;
    }
    setSourceFiles(merged);
    setText('');
  }, [sourceFiles, queueStatus]);

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

    selectSourceFiles(event.dataTransfer.files);
  }, [selectSourceFiles]);

  const loadSessions = useCallback(async (showLoading = true) => {
    try {
      if (showLoading) setIsLoadingSessions(true);
      const response = await optimizationAPI.listSessions();
      setSessions(response.data);

    } catch (error) {
      console.error('加载会话失败:', error);
    } finally {
      if (showLoading) setIsLoadingSessions(false);
    }
  }, []);

  const loadQueueStatus = useCallback(async (sessionId = null) => {
    try {
      const response = await optimizationAPI.getQueueStatus(sessionId);
      setQueueStatus(response.data);
    } catch (error) {
      console.error('加载队列状态失败:', error);
    }
  }, []);

  useEffect(() => {
    loadSessions();
    loadQueueStatus();
  }, [loadSessions, loadQueueStatus]);

  useEffect(() => {
    const interval = setInterval(loadQueueStatus, 15000);
    return () => clearInterval(interval);
  }, [loadQueueStatus]);

  useEffect(() => {
    const active = sessions.filter((session) => session.status === 'processing' || session.status === 'queued');
    if (active.length > 0) {
      const interval = setInterval(() => {
        loadSessions(false);
        loadQueueStatus(active.find((session) => session.status === 'queued')?.session_id || null);
      }, 4000);
      return () => clearInterval(interval);
    }
    return undefined;
  }, [sessions, loadSessions, loadQueueStatus]);

  const handleStartOptimization = useCallback(async () => {
    if (!text.trim() && sourceFiles.length === 0) {
      toast.error('请输入文本或选择要优化的文件');
      return;
    }

    if (isSubmitting) {
      return;
    }

    try {
      setIsSubmitting(true);
      const response = sourceFiles.length > 0
        ? await optimizationAPI.startFileBatch(sourceFiles, processingMode)
        : await optimizationAPI.startOptimization({
            original_text: text,
            processing_mode: processingMode,
          });

      if (sourceFiles.length > 0) {
        const acceptedCount = response.data?.accepted?.length || 0;
        const rejectedCount = response.data?.rejected?.length || 0;
        const queuedCount = response.data?.queued_count || 0;
        toast.success(`已提交 ${acceptedCount} 个文件${queuedCount ? `，${queuedCount} 个进入排队` : ''}`);
        if (rejectedCount) {
          const names = response.data.rejected.slice(0, 3).map((item) => item.filename).join('、');
          toast.error(`${names}${rejectedCount > 3 ? ` 等 ${rejectedCount} 个文件` : ''}未通过校验`);
        }
      } else {
        toast.success('优化任务已提交');
      }
      setText('');
      setSourceFiles([]);
      loadSessions();
      loadQueueStatus();
    } catch (error) {
      const detail = error.response?.data?.detail;
      toast.error('启动优化失败: ' + (typeof detail === 'string' ? detail : detail?.message || '请稍后重试'));
    } finally {
      setIsSubmitting(false);
    }
  }, [text, sourceFiles, processingMode, isSubmitting, loadSessions, loadQueueStatus]);

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

  const handleBatchExport = useCallback(async (batch) => {
    if (!batch.sessions.every((session) => session.status === 'completed')) {
      toast.error('该批次还有未完成任务');
      return;
    }
    if (!window.confirm('确认已审核该批次内容并承担最终文档责任后导出吗？')) {
      return;
    }
    try {
      setExportingBatchId(batch.id);
      const response = await optimizationAPI.exportBatch(batch.sessions.map((session) => session.session_id));
      const disposition = response.headers['content-disposition'] || '';
      const encodedName = disposition.match(/filename\*=UTF-8''([^;]+)/i)?.[1];
      const filename = encodedName ? decodeURIComponent(encodedName) : `文衡批量优化_${batch.id.slice(0, 8)}.zip`;
      const url = window.URL.createObjectURL(response.data);
      const link = document.createElement('a');
      link.href = url;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.URL.revokeObjectURL(url);
      toast.success('批量文件已导出');
    } catch (error) {
      let detail = '批量导出失败';
      if (error.response?.data instanceof Blob) {
        try {
          const payload = JSON.parse(await error.response.data.text());
          detail = payload.detail || detail;
        } catch {
          detail = '批量导出文件生成失败';
        }
      }
      toast.error(detail);
    } finally {
      setExportingBatchId(null);
    }
  }, []);

  const activeSessions = useMemo(() => (
    sessions.filter((session) => session.status === 'processing' || session.status === 'queued')
  ), [sessions]);
  const processingSessions = useMemo(() => activeSessions.filter((session) => session.status === 'processing'), [activeSessions]);
  const queuedSessions = useMemo(() => activeSessions.filter((session) => session.status === 'queued'), [activeSessions]);
  const activeSession = processingSessions[0]?.session_id || queuedSessions[0]?.session_id || null;
  const currentActiveSessionData = processingSessions[0] || queuedSessions[0] || null;
  const canSubmit = queueStatus?.can_submit ?? true;

  const batchGroups = useMemo(() => {
    const groups = new Map();
    sessions.forEach((session) => {
      if (!session.batch_id) return;
      if (!groups.has(session.batch_id)) {
        groups.set(session.batch_id, { id: session.batch_id, sessions: [], createdAt: session.created_at });
      }
      groups.get(session.batch_id).sessions.push(session);
    });
    return Array.from(groups.values())
      .sort((left, right) => new Date(right.createdAt) - new Date(left.createdAt))
      .slice(0, 5);
  }, [sessions]);

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
                ? `处理中 ${processingSessions.length}/${queueStatus?.user_task_limit || 1} · 排队 ${queuedSessions.length}`
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

        <div className="grid min-w-0 grid-cols-[minmax(0,1fr)] gap-4 xl:grid-cols-[minmax(0,1fr)_320px]">
          <div className="min-w-0 space-y-4">
            <section className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
              <div className="flex items-center justify-between gap-3 border-b border-slate-200 px-4 py-3.5">
                <h2 className="text-base font-semibold">新建处理任务</h2>
                <span className="inline-flex shrink-0 items-center gap-1.5 rounded bg-emerald-50 px-2 py-1 text-xs font-semibold text-emerald-700">
                  <Activity className="h-3.5 w-3.5" />
                  {activeSessions.length > 0
                    ? `运行 ${processingSessions.length}/${queueStatus?.user_task_limit || 1} · 排队 ${queuedSessions.length}`
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
                  aria-label="添加导入文件"
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
                        <p className="text-sm font-semibold text-emerald-800">松开即可加入批量任务</p>
                        <p className="mt-0.5 text-xs text-emerald-700">支持一次拖入多个文件</p>
                      </>
                    ) : sourceFiles.length > 0 ? (
                      <>
                        <p className="text-sm font-semibold text-slate-800">已选择 {sourceFiles.length} 个文件</p>
                        <p className="mt-0.5 text-xs text-slate-500">
                          {(sourceFiles.reduce((sum, file) => sum + file.size, 0) / 1024 / 1024).toFixed(2)} MB · 超出并发限制的任务自动排队
                        </p>
                      </>
                    ) : (
                      <>
                        <p className="text-sm font-semibold text-slate-700">批量导入并按原格式回写</p>
                        <p className="mt-0.5 text-xs text-slate-500">
                          DOCX、PDF、TXT、MD · 单文件 {queueStatus?.max_upload_file_size_mb || 20} MB · 每批最多 {queueStatus?.max_batch_files || MAX_BATCH_FILES} 个
                        </p>
                      </>
                    )}
                  </div>
                  <div className="flex shrink-0 items-center gap-2">
                    {sourceFiles.length > 0 && (
                      <button
                        type="button"
                        onClick={(event) => {
                          event.stopPropagation();
                          setSourceFiles([]);
                        }}
                        className="inline-flex h-9 w-9 items-center justify-center rounded-md border border-slate-200 bg-white text-slate-500 hover:text-rose-600"
                        title="清空文件"
                      >
                        <X className="h-4 w-4" />
                      </button>
                    )}
                    <span className={`inline-flex h-9 items-center gap-2 rounded-md border bg-white px-3 text-sm font-semibold ${isDraggingFile ? 'border-emerald-300 text-emerald-700' : 'border-slate-300 text-slate-700'}`}>
                      <Upload className="h-4 w-4" />
                      {isDraggingFile ? '放置文件' : sourceFiles.length ? '继续添加' : '选择文件'}
                    </span>
                    <input
                      ref={fileInputRef}
                      type="file"
                      multiple
                      accept=".docx,.pdf,.txt,.md,text/plain,text/markdown,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document"
                      className="sr-only"
                      onChange={(event) => {
                        selectSourceFiles(event.target.files);
                        event.target.value = '';
                      }}
                    />
                  </div>
                </div>

                {sourceFiles.length > 0 && (
                  <div className="mt-2 overflow-hidden rounded-md border border-slate-200 bg-white">
                    <div className="flex items-center justify-between border-b border-slate-100 bg-slate-50 px-3 py-2">
                      <span className="inline-flex items-center gap-2 text-xs font-semibold text-slate-600">
                        <Files className="h-3.5 w-3.5" />
                        待提交文件
                      </span>
                      <span className="text-xs text-slate-400">{sourceFiles.length}/{queueStatus?.max_batch_files || MAX_BATCH_FILES}</span>
                    </div>
                    <div className="max-h-44 divide-y divide-slate-100 overflow-y-auto">
                      {sourceFiles.map((file) => (
                        <div key={`${file.name}:${file.size}:${file.lastModified}`} className="flex min-h-11 items-center gap-3 px-3 py-2">
                          <FileText className="h-4 w-4 shrink-0 text-slate-400" />
                          <div className="min-w-0 flex-1">
                            <p className="truncate text-sm font-medium text-slate-700">{file.name}</p>
                            <p className="text-xs text-slate-400">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
                          </div>
                          <button
                            type="button"
                            onClick={() => setSourceFiles((current) => current.filter((candidate) => candidate !== file))}
                            className="inline-flex h-8 w-8 items-center justify-center rounded-md text-slate-400 hover:bg-rose-50 hover:text-rose-600"
                            title="移除文件"
                          >
                            <X className="h-4 w-4" />
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                <div className="mt-3 overflow-hidden rounded-md border border-slate-300 bg-white focus-within:border-emerald-600 focus-within:ring-2 focus-within:ring-emerald-600/10">
                  <textarea
                    value={text}
                    onChange={(event) => {
                      setText(event.target.value);
                      if (event.target.value) setSourceFiles([]);
                    }}
                    disabled={sourceFiles.length > 0}
                    placeholder={sourceFiles.length ? '已选择批量文件，将分别读取并处理文字' : '在此粘贴需要处理的内容...'}
                    className="min-h-[220px] w-full resize-y bg-transparent px-4 py-3.5 text-base leading-7 text-slate-900 outline-none placeholder:text-slate-400 sm:min-h-[300px] lg:min-h-[340px]"
                  />
                  <div className="flex flex-col gap-2 border-t border-slate-200 bg-slate-50 px-3 py-2.5 sm:flex-row sm:items-center sm:justify-between">
                    <div className="flex items-center gap-3 text-xs text-slate-500">
                      <span>{sourceFiles.length ? `${sourceFiles.length} 个文件任务` : `${text.length.toLocaleString()} 字`}</span>
                      {!canSubmit && (
                        <span className="text-amber-700">
                          使用额度不足或任务队列已满
                        </span>
                      )}
                    </div>
                    <button
                      type="button"
                      onClick={handleStartOptimization}
                      disabled={(!text.trim() && sourceFiles.length === 0) || !canSubmit || isSubmitting}
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
                          {sourceFiles.length ? `提交 ${sourceFiles.length} 个任务` : '开始优化'}
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

            {batchGroups.length > 0 && (
              <section className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
                <div className="flex min-h-14 items-center justify-between border-b border-slate-200 px-4">
                  <div className="flex items-center gap-2.5">
                    <FileArchive className="h-4 w-4 text-slate-400" />
                    <h2 className="text-sm font-semibold text-slate-900">批量任务</h2>
                  </div>
                  <span className="text-xs text-slate-400">最近 {batchGroups.length} 批</span>
                </div>
                <div className="divide-y divide-slate-100">
                  {batchGroups.map((batch) => {
                    const completed = batch.sessions.filter((session) => session.status === 'completed').length;
                    const processing = batch.sessions.filter((session) => session.status === 'processing').length;
                    const queued = batch.sessions.filter((session) => session.status === 'queued').length;
                    const failed = batch.sessions.filter((session) => ['failed', 'stopped'].includes(session.status)).length;
                    const allCompleted = completed === batch.sessions.length;
                    const progress = batch.sessions.reduce((sum, session) => sum + Number(session.progress || 0), 0) / batch.sessions.length;
                    return (
                      <div key={batch.id} className="px-4 py-3.5">
                        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                          <div className="min-w-0 flex-1">
                            <div className="flex min-w-0 items-center gap-2">
                              <span className="truncate text-sm font-semibold text-slate-800">
                                {batch.sessions[0]?.source_filename || '批量文档'}
                              </span>
                              {batch.sessions.length > 1 && (
                                <span className="shrink-0 text-xs text-slate-400">等 {batch.sessions.length} 个文件</span>
                              )}
                            </div>
                            <div className="mt-1.5 flex flex-wrap items-center gap-x-3 gap-y-1 text-xs">
                              <span className="text-emerald-700">完成 {completed}</span>
                              <span className="text-sky-700">处理 {processing}</span>
                              <span className="text-amber-700">排队 {queued}</span>
                              {failed > 0 && <span className="text-rose-700">异常 {failed}</span>}
                            </div>
                            <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-100">
                              <div className="h-full rounded-full bg-emerald-500 transition-all duration-500" style={{ width: `${progress}%` }} />
                            </div>
                          </div>
                          <button
                            type="button"
                            onClick={() => handleBatchExport(batch)}
                            disabled={!allCompleted || exportingBatchId === batch.id}
                            className="inline-flex h-9 shrink-0 items-center justify-center gap-2 rounded-md border border-slate-300 bg-white px-3 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:cursor-not-allowed disabled:border-slate-200 disabled:text-slate-400"
                          >
                            {exportingBatchId === batch.id ? (
                              <RefreshCw className="h-4 w-4 animate-spin" />
                            ) : (
                              <Download className="h-4 w-4" />
                            )}
                            {allCompleted ? '下载全部' : failed ? '存在异常' : '等待完成'}
                          </button>
                        </div>
                      </div>
                    );
                  })}
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

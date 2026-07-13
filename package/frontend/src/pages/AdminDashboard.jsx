import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { APP_NAME } from '../branding';
import axios from 'axios';
import { toast } from 'react-hot-toast';
import {
  LogIn,
  LogOut,
  Users,
  Key,
  Trash2,
  CheckCircle,
  XCircle,
  Shield,
  Plus,
  TrendingUp,
  Activity,
  Eye,
  Download,
  RefreshCw,
  Settings,
  BarChart3,
  Database,
  Edit2,
  Clock,
  FileText,
  Loader2
} from 'lucide-react';
import ConfigManager from '../components/ConfigManager';
import SessionMonitor from '../components/SessionMonitor';
import DatabaseManager from '../components/DatabaseManager';

const TAB_ITEMS = [
  { id: 'dashboard', label: '数据面板', icon: BarChart3 },
  { id: 'sessions', label: '会话监控', icon: Activity },
  { id: 'database', label: '数据库管理', icon: Database },
  { id: 'config', label: '系统配置', icon: Settings }
];

const METRIC_TONES = {
  slate: {
    icon: 'bg-slate-100 text-slate-600',
    detail: 'bg-slate-100 text-slate-600'
  },
  blue: {
    icon: 'bg-blue-50 text-blue-600',
    detail: 'bg-blue-50 text-blue-700'
  },
  green: {
    icon: 'bg-emerald-50 text-emerald-600',
    detail: 'bg-emerald-50 text-emerald-700'
  },
  amber: {
    icon: 'bg-amber-50 text-amber-600',
    detail: 'bg-amber-50 text-amber-700'
  },
  teal: {
    icon: 'bg-teal-50 text-teal-600',
    detail: 'bg-teal-50 text-teal-700'
  },
  rose: {
    icon: 'bg-rose-50 text-rose-600',
    detail: 'bg-rose-50 text-rose-700'
  }
};

const MetricCard = ({ label, value, icon: Icon, detail, tone = 'blue', suffix }) => {
  const colors = METRIC_TONES[tone] || METRIC_TONES.blue;

  return (
    <div className="min-w-0 rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="truncate text-xs font-medium text-slate-500">{label}</p>
          <p className="mt-1 text-2xl font-semibold text-slate-950">
            {value}
            {suffix && <span className="ml-1 text-xs font-medium text-slate-500">{suffix}</span>}
          </p>
          {detail && (
            <span className={`mt-2 inline-flex rounded px-1.5 py-0.5 text-[11px] font-medium ${colors.detail}`}>
              {detail}
            </span>
          )}
        </div>
        <div className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-md ${colors.icon}`}>
          <Icon className="h-4.5 w-4.5" />
        </div>
      </div>
    </div>
  );
};

const DateTime = ({ value, emptyText = '从未使用' }) => {
  if (!value) {
    return <span className="text-slate-400">{emptyText}</span>;
  }

  const date = new Date(value);
  return (
    <span className="block leading-5">
      <span className="block text-slate-700">{date.toLocaleDateString('zh-CN')}</span>
      <span className="block text-xs text-slate-400">
        {date.toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}
      </span>
    </span>
  );
};

const AdminDashboard = () => {
  const navigate = useNavigate();
  const [isAuthenticated, setIsAuthenticated] = useState(false);
  const [loading, setLoading] = useState(false);
  const [adminToken, setAdminToken] = useState(localStorage.getItem('adminToken'));

  // Tab state
  const [activeTab, setActiveTab] = useState('dashboard');

  // Login form state
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');

  // Users state
  const [users, setUsers] = useState([]);
  const [loadingUsers, setLoadingUsers] = useState(false);

  // Statistics state
  const [statistics, setStatistics] = useState(null);
  const [loadingStats, setLoadingStats] = useState(false);

  // Card key generation state
  const [newCardKey, setNewCardKey] = useState('');
  const [generatedKey, setGeneratedKey] = useState('');

  // Batch generation state
  const [batchCount, setBatchCount] = useState(5);
  const [batchPrefix, setBatchPrefix] = useState('');
  const [batchUsageLimit, setBatchUsageLimit] = useState(1);
  const [showBatchModal, setShowBatchModal] = useState(false);

  // Edit usage limit modal
  const [editingUserId, setEditingUserId] = useState(null);
  const [newUsageLimit, setNewUsageLimit] = useState('');
  const [newTaskConcurrencyLimit, setNewTaskConcurrencyLimit] = useState('1');

  // User details modal
  const [selectedUser, setSelectedUser] = useState(null);
  const [userDetails, setUserDetails] = useState(null);
  const [showUserDetails, setShowUserDetails] = useState(false);

  useEffect(() => {
    if (adminToken) {
      verifyToken();
    }
  }, [adminToken]);

  useEffect(() => {
    if (isAuthenticated) {
      fetchStatistics();
      // 每30秒自动刷新统计数据
      const interval = setInterval(fetchStatistics, 30000);
      return () => clearInterval(interval);
    }
  }, [isAuthenticated]);

  const verifyToken = async () => {
    try {
      await axios.post('/api/admin/verify-token', {}, {
        headers: { Authorization: `Bearer ${adminToken}` }
      });
      setIsAuthenticated(true);
      fetchUsers();
    } catch (error) {
      localStorage.removeItem('adminToken');
      setAdminToken(null);
      setIsAuthenticated(false);
    }
  };

  const handleLogin = async (e) => {
    e.preventDefault();
    setLoading(true);

    try {
      const response = await axios.post('/api/admin/login', {
        username,
        password
      });

      const { access_token } = response.data;
      localStorage.setItem('adminToken', access_token);
      setAdminToken(access_token);
      setIsAuthenticated(true);
      toast.success('登录成功！');
      fetchUsers();
    } catch (error) {
      toast.error(error.response?.data?.detail || '登录失败，请检查用户名和密码');
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('adminToken');
    setAdminToken(null);
    setIsAuthenticated(false);
    setUsername('');
    setPassword('');
    toast.success('已退出登录');
  };

  const fetchUsers = async () => {
    setLoadingUsers(true);
    try {
      const response = await axios.get('/api/admin/users', {
        headers: { Authorization: `Bearer ${adminToken}` }
      });
      setUsers(response.data);
    } catch (error) {
      toast.error('获取用户列表失败');
      console.error('Error fetching users:', error);
    } finally {
      setLoadingUsers(false);
    }
  };

  const fetchStatistics = async () => {
    setLoadingStats(true);
    try {
      const response = await axios.get('/api/admin/statistics', {
        headers: { Authorization: `Bearer ${adminToken}` }
      });
      setStatistics(response.data);
    } catch (error) {
      console.error('Error fetching statistics:', error);
    } finally {
      setLoadingStats(false);
    }
  };

  const handleGenerateCardKey = async (e) => {
    e.preventDefault();
    if (!newCardKey.trim()) {
      toast.error('请输入卡密');
      return;
    }

    try {
      const response = await axios.post('/api/admin/card-keys',
        { card_key: newCardKey },
        { headers: { Authorization: `Bearer ${adminToken}` } }
      );

      setGeneratedKey(response.data.card_key);
      setNewCardKey('');
      toast.success('卡密生成成功！');
      fetchUsers();
    } catch (error) {
      toast.error(error.response?.data?.detail || '生成卡密失败');
    }
  };

  const handleToggleUserStatus = async (userId, currentStatus) => {
    try {
      await axios.patch(`/api/admin/users/${userId}/toggle`,
        {},
        { headers: { Authorization: `Bearer ${adminToken}` } }
      );
      toast.success(currentStatus ? '用户已禁用' : '用户已启用');
      fetchUsers();
    } catch (error) {
      toast.error('操作失败');
    }
  };

  const handleDeleteUser = async (userId) => {
    if (!window.confirm('确定要删除这个用户吗？此操作不可撤销。')) {
      return;
    }

    try {
      await axios.delete(`/api/admin/users/${userId}`, {
        headers: { Authorization: `Bearer ${adminToken}` }
      });
      toast.success('用户已删除');
      fetchUsers();
    } catch (error) {
      toast.error('删除用户失败');
    }
  };

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text);
    toast.success('已复制到剪贴板');
  };

  const handleBatchGenerate = async () => {
    if (batchCount <= 0 || batchCount > 100) {
      toast.error('批量生成数量必须在 1-100 之间');
      return;
    }

    try {
      const response = await axios.post('/api/admin/batch-generate-keys',
        null,
        {
          params: {
            count: batchCount,
            prefix: batchPrefix,
            usage_limit: batchUsageLimit
          },
          headers: { Authorization: `Bearer ${adminToken}` }
        }
      );

      toast.success(`成功生成 ${response.data.count} 个卡密`);
      setShowBatchModal(false);
      setBatchCount(5);
      setBatchPrefix('');
      setBatchUsageLimit(1);
      fetchUsers();
      fetchStatistics();
    } catch (error) {
      toast.error(error.response?.data?.detail || '批量生成失败');
    }
  };

  const handleUpdateUsageLimit = async (userId, newLimit) => {
    try {
      await axios.patch(
        `/api/admin/users/${userId}/usage`,
        {
          usage_limit: parseInt(newLimit),
          task_concurrency_limit: parseInt(newTaskConcurrencyLimit),
        },
        { headers: { Authorization: `Bearer ${adminToken}` } }
      );
      toast.success('使用次数已更新');
      setEditingUserId(null);
      setNewUsageLimit('');
      setNewTaskConcurrencyLimit('1');
      fetchUsers();
    } catch (error) {
      toast.error(error.response?.data?.detail || '更新失败');
    }
  };

  const handleViewUserDetails = async (userId) => {
    try {
      const response = await axios.get(`/api/admin/users/${userId}/details`, {
        headers: { Authorization: `Bearer ${adminToken}` }
      });
      setUserDetails(response.data);
      setSelectedUser(userId);
      setShowUserDetails(true);
    } catch (error) {
      toast.error('获取用户详情失败');
    }
  };

  const exportUsersToCSV = () => {
    const headers = ['卡密', '状态', '创建时间', '最后使用'];
    const rows = users.map(user => [
      user.card_key,
      user.is_active ? '启用' : '禁用',
      new Date(user.created_at).toLocaleString('zh-CN'),
      user.last_used ? new Date(user.last_used).toLocaleString('zh-CN') : '从未使用'
    ]);

    const csvContent = [
      headers.join(','),
      ...rows.map(row => row.join(','))
    ].join('\n');

    const blob = new Blob(['\ufeff' + csvContent], { type: 'text/csv;charset=utf-8;' });
    const link = document.createElement('a');
    link.href = URL.createObjectURL(blob);
    link.download = `users_${new Date().toISOString().split('T')[0]}.csv`;
    link.click();
    toast.success('用户数据已导出');
  };

  // Login Page
  if (!isAuthenticated) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 to-cyan-50 flex items-center justify-center p-4">
        <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-8 animate-fade-in-up">
          <div className="flex items-center justify-center mb-8">
            <div className="bg-blue-600 p-3 rounded-full">
              <Shield className="w-8 h-8 text-white" />
            </div>
          </div>
          <h1 className="text-3xl font-bold text-center mb-2 text-gray-800">
            {APP_NAME} 管理台
          </h1>
          <p className="text-center text-gray-600 mb-8">
            使用管理员账号进入系统管理
          </p>

          <form onSubmit={handleLogin} className="space-y-6">
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                用户名
              </label>
              <input
                type="text"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="请输入用户名"
                required
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                密码
              </label>
              <input
                type="password"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full px-4 py-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                placeholder="请输入密码"
                required
              />
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full bg-blue-600 hover:bg-blue-700 disabled:bg-gray-400 text-white font-semibold py-3 rounded-lg transition-colors flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  登录中...
                </>
              ) : (
                <>
                  <LogIn className="w-5 h-5" />
                  登录
                </>
              )}
            </button>
          </form>

          <div className="mt-6 text-center">
            <button
              onClick={() => navigate('/')}
              className="text-blue-600 hover:text-blue-700 text-sm"
            >
              返回首页
            </button>
          </div>
        </div>
      </div>
    );
  }

  // Admin Dashboard
  return (
    <div className="min-h-screen bg-slate-50 text-slate-900">
      {/* Header */}
      <div className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex h-16 max-w-[1600px] items-center justify-between px-4 sm:px-6">
            <div className="flex min-w-0 items-center gap-3">
              <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-md bg-blue-50">
                <Shield className="h-5 w-5 text-blue-600" />
              </div>
              <div className="min-w-0">
                <h1 className="truncate text-lg font-semibold text-slate-950 sm:text-xl">{APP_NAME} 管理台</h1>
                <p className="hidden text-xs text-slate-500 sm:block">运行状态与访问权限管理</p>
              </div>
            </div>
            <button
              onClick={handleLogout}
              className="flex h-9 shrink-0 items-center gap-2 rounded-md border border-red-200 bg-white px-3 text-sm font-medium text-red-600 transition-colors hover:bg-red-50"
              title="退出登录"
            >
              <LogOut className="h-4 w-4" />
              <span className="hidden sm:inline">退出登录</span>
            </button>
        </div>
      </div>

      {/* Tabs Navigation */}
      <div className="border-b border-slate-200 bg-white">
        <div className="mx-auto max-w-[1600px] px-4 sm:px-6">
          <div className="grid grid-cols-2 gap-1 py-2 sm:flex sm:overflow-x-auto sm:[scrollbar-width:none] sm:[&::-webkit-scrollbar]:hidden">
            {TAB_ITEMS.map(({ id, label, icon: Icon }) => (
              <button
                key={id}
                onClick={() => setActiveTab(id)}
                className={`flex h-10 w-full items-center justify-center gap-2 rounded-md px-3 text-sm font-medium transition-colors sm:w-auto sm:shrink-0 sm:px-4 ${
                  activeTab === id
                    ? 'bg-blue-600 text-white'
                    : 'text-slate-600 hover:bg-slate-100 hover:text-slate-950'
                }`}
              >
                <Icon className="h-4 w-4" />
                <span>{label}</span>
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-[1600px] px-4 py-5 sm:px-6 sm:py-6">
        {/* Tab Content */}
        {activeTab === 'dashboard' && (
          <>
            {/* Statistics Cards */}
            {statistics && (
              <>
                <div className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
                  <MetricCard
                    label="总用户数"
                    value={statistics.users.total}
                    detail={`+${statistics.users.today_new} 今日`}
                    icon={Users}
                    tone="slate"
                  />
                  <MetricCard
                    label="启用用户"
                    value={statistics.users.active}
                    detail={`${statistics.users.inactive} 禁用`}
                    icon={CheckCircle}
                    tone="green"
                  />
                  <MetricCard
                    label="今日活跃"
                    value={statistics.users.today_active}
                    detail={`${statistics.users.recent_active_7days} 近 7 日`}
                    icon={Activity}
                    tone="blue"
                  />
                  <MetricCard
                    label="总会话数"
                    value={statistics.sessions.total}
                    detail={`${statistics.sessions.today} 今日`}
                    icon={Database}
                    tone="blue"
                  />
                </div>

                {statistics.processing && (
                  <div className="mb-4 grid grid-cols-2 gap-3 lg:grid-cols-4">
                    <MetricCard
                      label="处理字符数"
                      value={statistics.processing.total_chars_processed.toLocaleString()}
                      detail="累计"
                      icon={BarChart3}
                      tone="blue"
                    />
                    <MetricCard
                      label="平均处理耗时"
                      value={Math.round(statistics.processing.avg_processing_time)}
                      suffix="秒"
                      detail="平均"
                      icon={Clock}
                      tone="amber"
                    />
                    <MetricCard
                      label="论文润色"
                      value={statistics.processing.paper_polish_count}
                      detail="任务数"
                      icon={FileText}
                      tone="teal"
                    />
                    <MetricCard
                      label="润色 + 增强"
                      value={statistics.processing.paper_polish_enhance_count}
                      detail="任务数"
                      icon={TrendingUp}
                      tone="rose"
                    />
                  </div>
                )}

                {statistics.word_formatter && (
                  <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-3 xl:grid-cols-5">
                    <MetricCard label="排版任务" value={statistics.word_formatter.total} icon={FileText} tone="slate" />
                    <MetricCard label="已完成" value={statistics.word_formatter.completed} icon={CheckCircle} tone="green" />
                    <MetricCard label="运行中" value={statistics.word_formatter.running} icon={Loader2} tone="blue" />
                    <MetricCard label="等待中" value={statistics.word_formatter.pending} icon={Clock} tone="amber" />
                    <MetricCard label="失败" value={statistics.word_formatter.failed} icon={XCircle} tone="rose" />
                  </div>
                )}
              </>
            )}

            <div className="grid grid-cols-1 gap-4 xl:grid-cols-[320px_minmax(0,1fr)] xl:items-start">
              {/* Card Key Generation */}
              <div>
                <div className="rounded-lg border border-slate-200 bg-white p-5 shadow-sm">
                  <div className="mb-5 flex items-center gap-3">
                    <div className="flex h-9 w-9 items-center justify-center rounded-md bg-blue-50">
                      <Key className="h-4 w-4 text-blue-600" />
                    </div>
                    <div>
                      <h2 className="text-base font-semibold text-slate-950">生成卡密</h2>
                      <p className="text-xs text-slate-500">创建单个或批量访问凭证</p>
                    </div>
                  </div>

                  <form onSubmit={handleGenerateCardKey} className="space-y-3">
                    <div>
                      <label className="mb-1.5 block text-xs font-medium text-slate-600">
                        卡密内容
                      </label>
                      <input
                        type="text"
                        value={newCardKey}
                        onChange={(e) => setNewCardKey(e.target.value)}
                        className="h-10 w-full rounded-md border border-slate-300 bg-white px-3 text-sm outline-none transition-colors placeholder:text-slate-400 focus:border-blue-500 focus:ring-2 focus:ring-blue-100"
                        placeholder="输入自定义卡密"
                      />
                    </div>

                    <button
                      type="submit"
                      className="flex h-10 w-full items-center justify-center gap-2 rounded-md bg-blue-600 text-sm font-medium text-white transition-colors hover:bg-blue-700"
                    >
                      <Plus className="w-4 h-4" />
                      生成卡密
                    </button>

                    <button
                      type="button"
                      onClick={() => setShowBatchModal(true)}
                      className="flex h-10 w-full items-center justify-center gap-2 rounded-md border border-slate-300 bg-white text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50"
                    >
                      <Key className="w-4 h-4" />
                      批量生成
                    </button>
                  </form>

                  {generatedKey && (
                    <div className="mt-4 rounded-md border border-emerald-200 bg-emerald-50 p-3">
                      <p className="mb-2 text-xs font-medium text-emerald-700">生成的卡密</p>
                      <div className="flex items-center gap-2">
                        <code className="min-w-0 flex-1 break-all rounded border border-emerald-200 bg-white px-2.5 py-2 font-mono text-xs text-emerald-800">
                          {generatedKey}
                        </code>
                        <button
                          onClick={() => copyToClipboard(generatedKey)}
                          className="h-9 shrink-0 rounded-md bg-emerald-600 px-3 text-sm font-medium text-white transition-colors hover:bg-emerald-700"
                        >
                          复制
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              </div>

              {/* Users List */}
              <div className="min-w-0">
                <div className="overflow-hidden rounded-lg border border-slate-200 bg-white shadow-sm">
                  <div className="border-b border-slate-200 p-4">
                    <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                      <div className="flex items-center gap-3">
                        <div className="flex h-9 w-9 items-center justify-center rounded-md bg-slate-100">
                          <Users className="h-4 w-4 text-slate-600" />
                        </div>
                        <div>
                          <h2 className="text-base font-semibold text-slate-950">用户管理</h2>
                          <p className="text-xs text-slate-500">共 {users.length} 个访问凭证</p>
                        </div>
                      </div>
                      <div className="grid grid-cols-2 gap-2 sm:flex">
                        <button
                          onClick={exportUsersToCSV}
                          className="flex h-9 items-center justify-center gap-2 rounded-md border border-slate-300 bg-white px-3 text-sm font-medium text-slate-700 transition-colors hover:bg-slate-50"
                        >
                          <Download className="w-4 h-4" />
                          导出CSV
                        </button>
                        <button
                          onClick={() => { fetchUsers(); fetchStatistics(); }}
                          disabled={loadingUsers}
                          className="flex h-9 items-center justify-center gap-2 rounded-md bg-blue-600 px-3 text-sm font-medium text-white transition-colors hover:bg-blue-700 disabled:bg-slate-400"
                        >
                          <RefreshCw className={`w-4 h-4 ${loadingUsers ? 'animate-spin' : ''}`} />
                          刷新
                        </button>
                      </div>
                    </div>
                  </div>

                  {loadingUsers ? (
                    <div className="flex items-center justify-center py-12">
                      <div className="h-7 w-7 animate-spin rounded-full border-2 border-blue-600 border-t-transparent" />
                    </div>
                  ) : users.length === 0 ? (
                    <div className="py-12 text-center text-sm text-slate-500">
                      暂无用户数据
                    </div>
                  ) : (
                    <>
                      <div className="hidden lg:block">
                        <table className="w-full table-fixed">
                          <colgroup>
                            <col className="w-[23%]" />
                            <col className="w-[14%]" />
                            <col className="w-[18%]" />
                            <col className="w-[18%]" />
                            <col className="w-[11%]" />
                            <col className="w-[16%]" />
                          </colgroup>
                          <thead className="border-b border-slate-200 bg-slate-50">
                            <tr>
                              {['卡密', '使用次数', '创建时间', '最后使用', '状态', '操作'].map((label) => (
                                <th key={label} className="px-3 py-2.5 text-left text-xs font-medium text-slate-500">
                                  {label}
                                </th>
                              ))}
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-slate-200 bg-white">
                            {users.map((user) => (
                              <tr key={user.id} className="transition-colors hover:bg-slate-50">
                                <td className="min-w-0 px-3 py-3">
                                  <code
                                    className="block truncate font-mono text-xs text-slate-900"
                                    title={user.card_key}
                                  >
                                    {user.card_key}
                                  </code>
                                </td>
                                <td className="px-3 py-3 text-sm">
                                  {editingUserId === user.id ? (
                                    <div className="flex items-center gap-1">
                                      <input
                                        type="number"
                                        value={newUsageLimit}
                                        onChange={(e) => setNewUsageLimit(e.target.value)}
                                        className="h-8 w-14 rounded border border-slate-300 px-1 text-center text-sm outline-none focus:border-blue-500"
                                        min="0"
                                      />
                                      <input
                                        type="number"
                                        value={newTaskConcurrencyLimit}
                                        onChange={(e) => setNewTaskConcurrencyLimit(e.target.value)}
                                        className="h-8 w-12 rounded border border-slate-300 px-1 text-center text-sm outline-none focus:border-blue-500"
                                        min="1"
                                        max="100"
                                        title="任务并发上限"
                                      />
                                      <button
                                        onClick={() => handleUpdateUsageLimit(user.id, newUsageLimit)}
                                        className="flex h-8 w-8 items-center justify-center rounded text-emerald-600 hover:bg-emerald-50"
                                        title="保存使用次数"
                                        aria-label="保存使用次数"
                                      >
                                        <CheckCircle className="h-4 w-4" />
                                      </button>
                                      <button
                                        onClick={() => {
                                          setEditingUserId(null);
                                          setNewUsageLimit('');
                                        }}
                                        className="flex h-8 w-8 items-center justify-center rounded text-slate-500 hover:bg-slate-100"
                                        title="取消编辑"
                                        aria-label="取消编辑"
                                      >
                                        <XCircle className="h-4 w-4" />
                                      </button>
                                    </div>
                                  ) : (
                                    <div className="flex min-w-0 items-center gap-1">
                                      <span className={`truncate text-sm font-medium ${
                                        user.usage_limit > 0 && user.usage_count >= user.usage_limit
                                          ? 'text-red-600'
                                          : user.usage_limit === 0
                                          ? 'text-emerald-600'
                                          : 'text-slate-700'
                                      }`}>
                                        {user.usage_count || 0} / {user.usage_limit === 0 ? '∞' : user.usage_limit}
                                        <span className="ml-2 text-xs font-normal text-slate-500">
                                          并发 {user.task_concurrency_limit || 1}
                                        </span>
                                      </span>
                                      <button
                                        onClick={() => {
                                          setEditingUserId(user.id);
                                          setNewUsageLimit(user.usage_limit ?? 1);
                                          setNewTaskConcurrencyLimit(user.task_concurrency_limit ?? 1);
                                        }}
                                        className="flex h-8 w-8 shrink-0 items-center justify-center rounded text-blue-600 hover:bg-blue-50"
                                        title="编辑使用次数限制"
                                        aria-label="编辑使用次数限制"
                                      >
                                        <Edit2 className="h-4 w-4" />
                                      </button>
                                    </div>
                                  )}
                                </td>
                                <td className="px-3 py-3 text-sm">
                                  <DateTime value={user.created_at} />
                                </td>
                                <td className="px-3 py-3 text-sm">
                                  <DateTime value={user.last_used} />
                                </td>
                                <td className="px-3 py-3">
                                  {user.is_active ? (
                                    <span className="inline-flex items-center gap-1 rounded bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-700">
                                      <CheckCircle className="h-3 w-3" />
                                      启用
                                    </span>
                                  ) : (
                                    <span className="inline-flex items-center gap-1 rounded bg-red-50 px-2 py-1 text-xs font-medium text-red-700">
                                      <XCircle className="h-3 w-3" />
                                      禁用
                                    </span>
                                  )}
                                </td>
                                <td className="px-3 py-3">
                                  <div className="flex items-center gap-1">
                                    <button
                                      onClick={() => handleViewUserDetails(user.id)}
                                      className="flex h-8 w-8 items-center justify-center rounded border border-slate-200 text-blue-600 transition-colors hover:bg-blue-50"
                                      title="查看详情"
                                      aria-label="查看详情"
                                    >
                                      <Eye className="h-4 w-4" />
                                    </button>
                                    <button
                                      onClick={() => handleToggleUserStatus(user.id, user.is_active)}
                                      className={`flex h-8 w-8 items-center justify-center rounded border transition-colors ${
                                        user.is_active
                                          ? 'border-amber-200 text-amber-600 hover:bg-amber-50'
                                          : 'border-emerald-200 text-emerald-600 hover:bg-emerald-50'
                                      }`}
                                      title={user.is_active ? '禁用用户' : '启用用户'}
                                      aria-label={user.is_active ? '禁用用户' : '启用用户'}
                                    >
                                      {user.is_active ? <XCircle className="h-4 w-4" /> : <CheckCircle className="h-4 w-4" />}
                                    </button>
                                    <button
                                      onClick={() => handleDeleteUser(user.id)}
                                      className="flex h-8 w-8 items-center justify-center rounded border border-red-200 text-red-600 transition-colors hover:bg-red-50"
                                      title="删除用户"
                                      aria-label="删除用户"
                                    >
                                      <Trash2 className="h-4 w-4" />
                                    </button>
                                  </div>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>

                      <div className="divide-y divide-slate-200 lg:hidden">
                        {users.map((user) => (
                          <div key={user.id} className="p-4">
                            <div className="flex items-start justify-between gap-3">
                              <code className="min-w-0 break-all font-mono text-xs text-slate-900">
                                {user.card_key}
                              </code>
                              {user.is_active ? (
                                <span className="inline-flex shrink-0 items-center gap-1 rounded bg-emerald-50 px-2 py-1 text-xs font-medium text-emerald-700">
                                  <CheckCircle className="h-3 w-3" />
                                  启用
                                </span>
                              ) : (
                                <span className="inline-flex shrink-0 items-center gap-1 rounded bg-red-50 px-2 py-1 text-xs font-medium text-red-700">
                                  <XCircle className="h-3 w-3" />
                                  禁用
                                </span>
                              )}
                            </div>

                            <div className="mt-4 grid grid-cols-2 gap-4 text-sm">
                              <div>
                                <p className="mb-1 text-xs text-slate-500">使用次数</p>
                                {editingUserId === user.id ? (
                                  <div className="flex items-center gap-1">
                                    <input
                                      type="number"
                                      value={newUsageLimit}
                                      onChange={(e) => setNewUsageLimit(e.target.value)}
                                      className="h-8 w-16 rounded border border-slate-300 px-1 text-center text-sm outline-none focus:border-blue-500"
                                      min="0"
                                    />
                                    <button
                                      onClick={() => handleUpdateUsageLimit(user.id, newUsageLimit)}
                                      className="flex h-8 w-8 items-center justify-center rounded text-emerald-600 hover:bg-emerald-50"
                                      aria-label="保存使用次数"
                                    >
                                      <CheckCircle className="h-4 w-4" />
                                    </button>
                                    <button
                                      onClick={() => {
                                        setEditingUserId(null);
                                        setNewUsageLimit('');
                                      }}
                                      className="flex h-8 w-8 items-center justify-center rounded text-slate-500 hover:bg-slate-100"
                                      aria-label="取消编辑"
                                    >
                                      <XCircle className="h-4 w-4" />
                                    </button>
                                  </div>
                                ) : (
                                  <div className="flex items-center gap-1">
                                    <span className="font-medium text-slate-800">
                                      {user.usage_count || 0} / {user.usage_limit === 0 ? '∞' : user.usage_limit}
                                    </span>
                                    <button
                                      onClick={() => {
                                        setEditingUserId(user.id);
                                        setNewUsageLimit(user.usage_limit ?? 1);
                                        setNewTaskConcurrencyLimit(user.task_concurrency_limit ?? 1);
                                      }}
                                      className="flex h-8 w-8 items-center justify-center rounded text-blue-600 hover:bg-blue-50"
                                      aria-label="编辑使用次数限制"
                                    >
                                      <Edit2 className="h-4 w-4" />
                                    </button>
                                  </div>
                                )}
                              </div>
                              <div>
                                <p className="mb-1 text-xs text-slate-500">创建时间</p>
                                <DateTime value={user.created_at} />
                              </div>
                              <div className="col-span-2">
                                <p className="mb-1 text-xs text-slate-500">最后使用</p>
                                <DateTime value={user.last_used} />
                              </div>
                            </div>

                            <div className="mt-4 grid grid-cols-3 gap-2">
                              <button
                                onClick={() => handleViewUserDetails(user.id)}
                                className="flex h-9 items-center justify-center gap-1.5 rounded-md border border-slate-200 text-xs font-medium text-blue-600 hover:bg-blue-50"
                              >
                                <Eye className="h-4 w-4" />
                                详情
                              </button>
                              <button
                                onClick={() => handleToggleUserStatus(user.id, user.is_active)}
                                className={`flex h-9 items-center justify-center gap-1.5 rounded-md border text-xs font-medium ${
                                  user.is_active
                                    ? 'border-amber-200 text-amber-600 hover:bg-amber-50'
                                    : 'border-emerald-200 text-emerald-600 hover:bg-emerald-50'
                                }`}
                              >
                                {user.is_active ? <XCircle className="h-4 w-4" /> : <CheckCircle className="h-4 w-4" />}
                                {user.is_active ? '禁用' : '启用'}
                              </button>
                              <button
                                onClick={() => handleDeleteUser(user.id)}
                                className="flex h-9 items-center justify-center gap-1.5 rounded-md border border-red-200 text-xs font-medium text-red-600 hover:bg-red-50"
                              >
                                <Trash2 className="h-4 w-4" />
                                删除
                              </button>
                            </div>
                          </div>
                        ))}
                      </div>
                    </>
                  )}
                </div>
              </div>
            </div>
          </>
        )}

        {/* Session Monitor Tab */}
        {activeTab === 'sessions' && (
          <SessionMonitor adminToken={adminToken} />
        )}

        {/* Database Manager Tab */}
        {activeTab === 'database' && (
          <DatabaseManager adminToken={adminToken} />
        )}

        {/* Config Manager Tab */}
        {activeTab === 'config' && (
          <ConfigManager adminToken={adminToken} />
        )}
      </div>

      {/* Batch Generation Modal */}
      {showBatchModal && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-md w-full p-6">
            <h3 className="text-xl font-bold text-gray-800 mb-4">批量生成卡密</h3>

            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  生成数量 (1-100)
                </label>
                <input
                  type="number"
                  min="1"
                  max="100"
                  value={batchCount}
                  onChange={(e) => setBatchCount(parseInt(e.target.value) || 1)}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  卡密前缀（可选）
                </label>
                <input
                  type="text"
                  value={batchPrefix}
                  onChange={(e) => setBatchPrefix(e.target.value)}
                  placeholder="例如: VIP-"
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  使用次数限制
                </label>
                <input
                  type="number"
                  min="0"
                  value={batchUsageLimit}
                  onChange={(e) => setBatchUsageLimit(parseInt(e.target.value) || 0)}
                  className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
                <p className="mt-1 text-xs text-gray-500">设置为 0 表示无限制使用</p>
              </div>
            </div>

            <div className="flex gap-3 mt-6">
              <button
                onClick={() => setShowBatchModal(false)}
                className="flex-1 px-4 py-2 bg-gray-200 hover:bg-gray-300 text-gray-800 rounded-lg transition-colors"
              >
                取消
              </button>
              <button
                onClick={handleBatchGenerate}
                className="flex-1 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
              >
                生成
              </button>
            </div>
          </div>
        </div>
      )}

      {/* User Details Modal */}
      {showUserDetails && userDetails && (
        <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-2xl max-w-2xl w-full p-6 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between mb-6">
              <h3 className="text-xl font-bold text-gray-800">用户详细信息</h3>
              <button
                onClick={() => setShowUserDetails(false)}
                className="text-gray-400 hover:text-gray-600"
              >
                <XCircle className="w-6 h-6" />
              </button>
            </div>

            {/* User Info */}
            <div className="bg-gray-50 rounded-lg p-4 mb-6">
              <h4 className="font-semibold text-gray-800 mb-3">基本信息</h4>
              <div className="grid grid-cols-2 gap-3 text-sm">
                <div>
                  <span className="text-gray-600">卡密：</span>
                  <code className="ml-2 font-mono text-blue-600">{userDetails.user.card_key}</code>
                </div>
                <div>
                  <span className="text-gray-600">状态：</span>
                  <span className={`ml-2 ${userDetails.user.is_active ? 'text-green-600' : 'text-red-600'}`}>
                    {userDetails.user.is_active ? '启用' : '禁用'}
                  </span>
                </div>
                <div>
                  <span className="text-gray-600">创建时间：</span>
                  <span className="ml-2">{new Date(userDetails.user.created_at).toLocaleString('zh-CN')}</span>
                </div>
                <div>
                  <span className="text-gray-600">最后使用：</span>
                  <span className="ml-2">
                    {userDetails.user.last_used
                      ? new Date(userDetails.user.last_used).toLocaleString('zh-CN')
                      : '从未使用'}
                  </span>
                </div>
              </div>
            </div>

            {/* Statistics */}
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
              <div className="bg-blue-50 rounded-lg p-4 text-center">
                <p className="text-2xl font-bold text-blue-600">{userDetails.statistics.total_sessions}</p>
                <p className="text-xs text-gray-600 mt-1">总会话数</p>
              </div>
              <div className="bg-green-50 rounded-lg p-4 text-center">
                <p className="text-2xl font-bold text-green-600">{userDetails.statistics.completed_sessions}</p>
                <p className="text-xs text-gray-600 mt-1">完成会话</p>
              </div>
              <div className="bg-blue-50 rounded-lg p-4 text-center">
                <p className="text-2xl font-bold text-blue-600">{userDetails.statistics.total_segments}</p>
                <p className="text-xs text-gray-600 mt-1">处理段落</p>
              </div>
              <div className="bg-orange-50 rounded-lg p-4 text-center">
                <p className="text-2xl font-bold text-orange-600">{userDetails.statistics.completed_segments}</p>
                <p className="text-xs text-gray-600 mt-1">完成段落</p>
              </div>
            </div>

            {/* Recent Sessions */}
            {userDetails.recent_sessions.length > 0 && (
              <div>
                <h4 className="font-semibold text-gray-800 mb-3">最近会话</h4>
                <div className="space-y-2">
                  {userDetails.recent_sessions.map((session) => (
                    <div key={session.id} className="bg-gray-50 rounded-lg p-3 flex items-center justify-between">
                      <div className="flex items-center gap-3">
                        <Activity className="w-4 h-4 text-gray-400" />
                        <div>
                          <p className="text-sm font-medium text-gray-800">会话 #{session.id}</p>
                          <p className="text-xs text-gray-500">
                            {new Date(session.created_at).toLocaleString('zh-CN')}
                          </p>
                        </div>
                      </div>
                      <span className={`px-2 py-1 rounded text-xs font-medium ${
                        session.status === 'completed'
                          ? 'bg-green-100 text-green-800'
                          : 'bg-yellow-100 text-yellow-800'
                      }`}>
                        {session.status === 'completed' ? '已完成' : '处理中'}
                      </span>
                    </div>
                  ))}
                </div>
              </div>
            )}

            <button
              onClick={() => setShowUserDetails(false)}
              className="w-full mt-6 px-4 py-2 bg-gray-200 hover:bg-gray-300 text-gray-800 rounded-lg transition-colors"
            >
              关闭
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default AdminDashboard;

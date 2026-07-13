import React from 'react';
import { Link } from 'react-router-dom';
import { ArrowLeft, Scale } from 'lucide-react';
import { APP_NAME } from '../branding';

const LegalPage = () => (
  <main className="min-h-screen bg-slate-50 text-slate-900">
    <div className="mx-auto max-w-3xl px-5 py-12 sm:px-8">
      <Link
        to="/"
        className="inline-flex items-center gap-2 text-sm font-medium text-slate-600 transition-colors hover:text-slate-950"
      >
        <ArrowLeft className="h-4 w-4" />
        返回登录
      </Link>

      <section className="mt-8 border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center bg-slate-900 text-white">
            <Scale className="h-5 w-5" />
          </div>
          <div>
            <h1 className="text-xl font-semibold">{APP_NAME} 开源许可</h1>
            <p className="mt-1 text-sm leading-6 text-slate-600">
              本服务基于开源软件构建，部署方对界面、品牌和运行配置进行了调整。
            </p>
          </div>
        </div>

        <div className="mt-8 space-y-5 text-sm leading-7 text-slate-700">
          <p>
            上游项目著作权归 Yan Wenxin 所有，采用
            {' '}
            <a
              className="font-medium text-slate-950 underline underline-offset-4"
              href="https://creativecommons.org/licenses/by-nc-sa/4.0/"
              target="_blank"
              rel="noreferrer"
            >
              CC BY-NC-SA 4.0
            </a>
            {' '}
            许可发布。
          </p>
          <p>
            本服务为非商业化部署。对上游项目所作的修改同样遵循 CC BY-NC-SA 4.0；使用本服务前，请自行核对适用的学术规范和机构要求。
          </p>
        </div>
      </section>
    </div>
  </main>
);

export default LegalPage;

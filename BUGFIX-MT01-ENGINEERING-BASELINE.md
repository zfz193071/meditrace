# MT-01 依赖与构建兼容修复

日期：2026-10-20。范围：工程基线，不改变旧诊断业务语义，不宣称新业务已完成。

## 问题与修复

1. 旧 Next 14 基线已不受支持，Next／React／类型依赖缺少一致的升级验证。升级锁定 Next 16.4.2、React 19.3.1；将 MarkdownRenderer 的旧全局 JSX 类型改为明确的 heading 标签联合类型；添加 jest-dom 类型声明，保留旧页面用例。
2. 根与后端重复 requirements 可能漂移，`vercel>=1.0.0` 没有可解析的对应版本且源码未使用。改为 pyproject + uv.lock 单源，导出带 hash 的 backend requirements，根仅转引；移除未用的全量 SDK。新增锁文件一致性检查。
3. 构建依赖 Google Fonts 外网，失败会阻断交付；改用既有系统字体栈。当前环境 Turbopack 的 PostCSS 子进程端口权限失败，固定使用 Next 官方支持的 Webpack 构建，未启动服务规避测试限制。
4. React／Next 升级后的 lint 要求内部链接使用 Link，修复首页三处导航。采用 ESLint 10 + 官方 Next plugin + typescript-eslint，避免启用已停止维护的 ESLint 9；旧代码警告只在原有文件范围放宽，新模块不放宽类型规则。
5. 安全审计发现 source-map-js 等间接依赖漏洞，添加精确 override 并重跑构建、测试。无补丁的开发依赖风险单列记录，没有用审计忽略参数掩盖结果。
6. 新模块对 Pydantic 校验失败返回固定错误，不回显患者原文；middleware 捕获运行异常，避免异常被 ASGI server 再抛出导致敏感 traceback。请求 ID 由服务端生成。

## 验证与限制

后端 39 项、前端 17 项、部署脚本 10 项通过；4 项 PostgreSQL 回归因无测试库跳过。前端 build／typecheck、契约确定性与漂移检测通过，生产依赖审计已知漏洞 0。完整命令、版本、大小与残余风险见 [MT-01 验收记录](docs/referral-review/MT-01-EVIDENCE.md)。

未自动浏览器发消息，未调用真实 AI，未改变线上部署。手动本地验证应使用新 `.venv` 依赖，后端修改后需由开发者手动重启；不要以本次基础测试代替 MT-22 的界面与业务验收。

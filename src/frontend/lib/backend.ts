/**
 * 后端地址解析（统一入口）
 *
 * 部署架构：Vercel Services —— Next.js 前端与 FastAPI 后端位于同一域名，
 * 后端通过仓库根目录 vercel.json 的 rewrites 挂载在 /api 前缀下。
 *
 * 约定的用法是「源地址 + 路径」：`${BACKEND_URL}/api/xxx`
 * 因此 NEXT_PUBLIC_BACKEND_URL 必须是「源地址」，不能带 /api 后缀。
 *
 * 取值规则：
 *   - 生产（推荐）   : 显式设为站点源地址，如 https://meditrace.baozaolaoba.top
 *   - 生产（不设置） : 退化为相对路径 ""，即 /api/xxx，同样走同域名，无需 CORS
 *   - 本地开发       : 未设置时回退到 http://localhost:8000
 */
const RAW = process.env.NEXT_PUBLIC_BACKEND_URL;

export const BACKEND_URL: string = (() => {
  if (!RAW || RAW.length === 0) {
    // 生产环境未配置时退化为相对路径，即 /api/xxx，同样走同域名
    return process.env.NODE_ENV === "production" ? "" : "http://localhost:8000";
  }
  // 防错：本项目约定总是拼接 `${BACKEND_URL}/api/xxx`，
  // 若有人误把地址写成 ".../api"（历史 .env.production 即为此值），
  // 会产生 /api/api/xxx，这里统一剥掉尾部的 /api。
  return RAW.replace(/\/+$/, "").replace(/\/api$/, "");
})();

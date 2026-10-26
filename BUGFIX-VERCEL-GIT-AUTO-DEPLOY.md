# 阻止 Git 推送绕过 V1 发布检查

日期：2026-10-26。归属：MT-21／MT-24。

## 问题与原因

只读检查 Vercel 项目发现 Git 自动部署开启、生产分支为 `main`，而仓库原先未设置 Git 部署限制。推送尚未验收的 V1 提交可能直接触发部署，绕过 `deploy-vercel.sh` 的前置与安全回退检查。

## 修复

在根 `vercel.json` 设置 `git.deploymentEnabled: false`，所有分支的 Git 自动部署禁用；CLI 发布仍由既有部署脚本控制。先推送独立验证分支运行 GitHub Actions，不推进远端生产 `main`。不修改供应商密钥、生产数据库或当前部署。

官方配置依据：https://vercel.com/docs/project-configuration/git-configuration。

## 验证

配置解析、部署工作流离线回归和独立分支推送后的平台状态由本次 CI 验收记录补充。该修复不代表 V1 已满足发布门槛，也不代表首次安全上线流程已经完成。

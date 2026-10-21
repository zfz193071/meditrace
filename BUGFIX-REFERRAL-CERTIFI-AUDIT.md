# Referral 依赖审计修复：certifi

日期：2026-10-21。归属：MT-05 依赖引入后的供应链验收。

## 复现与影响

执行 `src/backend/.venv/bin/pip-audit -r src/backend/requirements.txt --no-deps --disable-pip`，报告锁定的 `certifi==2026.10.18` 命中 `PYSEC-2026-4320`，修复版本为 `2026.10.19`。此包用于后端 HTTP 客户端的 TLS 信任链；本记录不声称应用已遭利用。

## 修复

仅对 certifi 执行定向依赖更新，锁定 `2026.10.19`，同步 `src/backend/uv.lock`、生成的 `requirements.txt` 与实际 `.venv`。保留其他依赖版本，不禁用证书校验或改用不安全 HTTP。命令：

```bash
src/backend/venv/bin/uv lock --project src/backend --upgrade-package certifi --cache-dir .uv-cache
src/backend/venv/bin/uv sync --project src/backend --frozen --cache-dir .uv-cache
src/backend/venv/bin/uv export --project src/backend --frozen --no-dev --no-emit-project --cache-dir .uv-cache --output-file src/backend/requirements.txt
```

验证结果与命令汇总见 [MT-05 验收证据](docs/referral-review/MT-05-EVIDENCE.md)。未部署、未启动服务、未修改生产环境。

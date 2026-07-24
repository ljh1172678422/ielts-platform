# 后端：Python 3.12 + uv + uvicorn
# 对齐 system-architecture §1.2：backend 服务，端口 8000（内部）
# Phase 12 生产加固：非 root 用户 + healthcheck + 生产依赖
FROM python:3.12-slim AS runtime

# 安装 uv（官方推荐，对齐本地 uv 0.11.7）
COPY --from=ghcr.io/astral-sh/uv:0.11.7 /uv /uvx /bin/

# 非 root 用户运行（最小权限原则）
RUN groupadd --gid 1001 app && useradd --uid 1001 --gid app --create-home app

WORKDIR /app

# 依赖层（先复制 lock 文件利用 Docker 缓存）
COPY --chown=app:app pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# 应用代码 + 迁移 + 脚本（db-init 服务需要 alembic + seed_admin）
COPY --chown=app:app app ./app
COPY --chown=app:app alembic.ini ./
COPY --chown=app:app migrations ./migrations
COPY --chown=app:app scripts ./scripts

# 录音存储目录（LocalStorageBackend，STORAGE_TYPE=local）
RUN mkdir -p /app/storage && chown app:app /app/storage

ENV APP_ENV=production \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

USER app
EXPOSE 8000

# healthcheck：/health 接口（main.py），200 视为健康
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request,sys; urllib.request.urlopen('http://localhost:8000/health', timeout=3); sys.exit(0)" || exit 1

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "2"]

# 后端：Python 3.12 + uv + uvicorn
# 对齐 system-architecture §1.2：backend 服务，端口 8000（内部）
FROM python:3.12-slim AS runtime

# 安装 uv（官方推荐，对齐本地 uv 0.11.7）
COPY --from=ghcr.io/astral-sh/uv:0.11.7 /uv /uvx /bin/

WORKDIR /app

# 依赖层（先复制 lock 文件利用 Docker 缓存）
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# 应用代码 + 迁移 + 脚本（db-init 服务需要 alembic + seed_admin）
COPY app ./app
COPY alembic.ini ./
COPY migrations ./migrations
COPY scripts ./scripts

ENV APP_ENV=production \
    PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uv", "run", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

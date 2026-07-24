# 部署指南（deploy.md）

> 本文回答："如何把 IELTS Speaking Web App 部署到生产 VPS。"
> 对齐 development-plan.md §14 任务 12.4、system-architecture.md §9、PROJECT_SPEC §8。
> 范围：单 VPS + Docker Compose + Nginx + Let's Encrypt HTTPS。
> 不在本文范围：多节点 / K8s / MinIO 集群 / CDN（MVP 之后）。

---

## 0. 部署架构速查

```text
                 ┌────────────────────────────────────────────┐
   Internet ───► │  VPS (Docker Compose)                      │
                 │                                            │
                 │   nginx (80/443)                           │
                 │     ├─ /            → user-web SPA         │
                 │     ├─ /admin/     → admin-web SPA         │
                 │     ├─ /api/       → backend:8000 (反代)   │
                 │     └─ /.well-known/ → Certbot webroot     │
                 │     (HTTPS 终止 + Let's Encrypt 证书)      │
                 │                                            │
                 │   backend (FastAPI, 内部 8000)              │
                 │     └─ 录音存储卷 backend-storage-prod     │
                 │                                            │
                 │   postgres:16 (内部 5432, pgdata-prod 卷)   │
                 └────────────────────────────────────────────┘
```

关键点（system-architecture §1.3）：

- 仅 `nginx` 暴露 80/443 给外网；`backend` / `postgres` 仅内部网络可达。
- `user-web` / `admin-web` 构建为静态文件，由 nginx 直接托管（无独立运行时容器）。
- 录音使用 `LocalStorageBackend`（`STORAGE_TYPE=local`），持久化到 Docker 卷。
- 启动顺序：`postgres` → `db-init`（alembic upgrade + seed_admin）→ `backend` → `nginx`。

---

## 1. 前置要求

### 1.1 服务器

| 项目 | 要求 |
| --- | --- |
| 操作系统 | Ubuntu 22.04 LTS / Debian 12（推荐） |
| CPU / 内存 | ≥ 2 vCPU / ≥ 2 GB RAM（MVP 规模） |
| 磁盘 | ≥ 20 GB（含录音存储；按用户量扩容） |
| 端口 | 80 / 443 开放（443 用于 HTTPS，80 用于 Certbot 验证 + HTTP 重定向） |
| 公网 IP | 固定 IP，已解析到域名（A 记录） |

### 1.2 域名

- 一个域名（例：`ielts.example.com`）已解析到 VPS 公网 IP。
- 子路径部署：用户端在 `/`，管理后台在 `/admin/`，无需额外子域名。

### 1.3 本地 / 服务器软件

```bash
# 服务器侧
docker --version          # ≥ 24.0
docker compose version    # v2（docker compose 插件，非旧版 docker-compose）
git --version             # 用于克隆仓库
```

如服务器未安装 Docker，参考官方一键脚本：

```bash
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER   # 注销重登生效
```

---

## 2. 获取代码

```bash
# 在 VPS 上
git clone https://github.com/<your-org>/ielts-speaking.git
cd ielts-speaking
git checkout main   # 生产始终从 main 部署
```

> 如使用私有仓库，需在服务器配置 SSH key 或 PAT 拉取权限。

---

## 3. 配置生产环境变量

### 3.1 复制模板

```bash
cp .env.production.example .env.production
```

### 3.2 生成强密钥

在 **本机**（非服务器）生成强随机值，粘贴到 `.env.production`：

```bash
# JWT_SECRET（32 字节随机串）
openssl rand -hex 32

# POSTGRES_PASSWORD（≥ 16 位，含字母+数字+符号）
openssl rand -base64 24 | tr -d '/+=' | head -c 24
```

### 3.3 编辑 `.env.production`

```ini
# ---------- PostgreSQL ----------
POSTGRES_USER=ielts
POSTGRES_PASSWORD=<上一步生成的强密码>
POSTGRES_DB=ielts_speaking

# ---------- JWT ----------
JWT_SECRET=<上一步生成的 32 字节随机串>
JWT_ALGORITHM=HS256
JWT_EXPIRES_SECONDS=86400

# ---------- CORS ----------
# 改为实际域名（HTTPS）
CORS_ORIGINS=["https://ielts.example.com"]

# ---------- 管理员初始化 ----------
# 密码≥12 位且含字母+数字（seed_admin.py 会校验）
SEED_ADMIN_EMAIL=admin@ielts.example.com
SEED_ADMIN_PASSWORD=<≥12 位 含字母+数字>
SEED_ADMIN_NICKNAME=Admin

# ---------- 存储 ----------
STORAGE_TYPE=local
STORAGE_LOCAL_PATH=/app/storage
```

**安全要点**：

- `.env.production` 已在 `.gitignore` 中，**切勿提交**。
- `JWT_SECRET` 泄露 = 所有 token 可被伪造；`POSTGRES_PASSWORD` 泄露 = 数据库被直连。
- 首次部署完成后，建议把 `.env.production` 备份到密码管理器（如 1Password / Bitwarden）。

### 3.4 修改 Nginx 证书路径（可选）

`nginx/nginx.conf` 中证书路径默认为 `/etc/letsencrypt/live/ielts/`。如需使用其他目录名（例：`live/ielts.example.com/`），修改以下两行：

```nginx
ssl_certificate     /etc/letsencrypt/live/<目录名>/fullchain.pem;
ssl_certificate_key /etc/letsencrypt/live/<目录名>/privkey.pem;
```

> 建议：保持目录名与 `certbot --cert-name` 一致，便于续签脚本统一管理。

---

## 4. 首次部署（含 HTTPS 证书签发）

Let's Encrypt 证书签发需先有 HTTP 80 端口可访问的 nginx，再用 webroot 模式验证。**首次部署分两步**：先用 bootstrap 配置（仅 HTTP）启动 → 签发证书 → 切换到 HTTPS 配置。

### 4.1 步骤 1：用 bootstrap 配置启动 nginx

bootstrap 配置（`nginx/nginx.bootstrap.conf`）仅监听 80，无 SSL，提供 ACME 验证入口 + 临时 HTTP 访问。

由于 `nginx/Dockerfile` 默认启用 HTTPS 主配置（`nginx.conf` → `default.conf`），首次部署需在启动后切换到 bootstrap：

```bash
# 在项目根目录
# 先仅启动 postgres + db-init + backend（不启动 nginx）
docker compose -f docker-compose.prod.yml --env-file .env.production up -d postgres db-init backend

# 等 backend 健康检查通过
docker compose -f docker-compose.prod.yml ps   # backend 状态应为 healthy

# 构建 + 启动 nginx（首次会因证书缺失启动失败，预期行为）
docker compose -f docker-compose.prod.yml up -d --build nginx

# 即使 nginx 启动失败，镜像已构建。手动覆盖为 bootstrap 配置并启动：
docker compose -f docker-compose.prod.yml run --rm --no-deps --entrypoint sh nginx -c \
  "cp /etc/nginx/conf.d/nginx.bootstrap.conf /etc/nginx/conf.d/default.conf && nginx"

# 或更稳妥：用一次性容器把 bootstrap 配置写入挂载卷后重启
# （本文采用镜像内文件直接覆盖方案，简单直接）
```

> **替代方案**（推荐）：首次部署前先在宿主机签发证书，再首次 `up` 即用 HTTPS 配置。见步骤 4.2。

### 4.2 步骤 2：签发 Let's Encrypt 证书

#### 方案 A：宿主机 Certbot（推荐，简单）

在 VPS 宿主机（非容器内）安装 certbot：

```bash
sudo apt update && sudo apt install -y certbot
```

签发证书（需 80 端口空闲，故先停 nginx 容器）：

```bash
# 停 nginx 容器释放 80 端口
docker compose -f docker-compose.prod.yml stop nginx

# 签发证书（standalone 模式，certbot 自己起临时 HTTP 服务）
sudo certbot certonly --standalone \
  -d ielts.example.com \
  --non-interactive --agree-tos -m admin@ielts.example.com

# 证书生成在 /etc/letsencrypt/live/ielts.example.com/
```

#### 方案 B：webroot 模式（nginx 在线时用）

如 nginx 已用 bootstrap 配置启动并占用 80：

```bash
sudo certbot certonly --webroot -w /var/www/certbot \
  -d ielts.example.com \
  --non-interactive --agree-tos -m admin@ielts.example.com
```

> webroot 目录 `/var/www/certbot` 是 `nginx` 容器内的路径，需保证宿主机对应目录存在并被容器挂载。`docker-compose.prod.yml` 已挂载 `certbot-webroot` 卷。

### 4.3 步骤 3：切换到 HTTPS 配置并重启

证书签发后，重启 nginx 容器加载 HTTPS 主配置：

```bash
# 重建 nginx 容器（使用默认的 HTTPS 配置 nginx.conf → default.conf）
docker compose -f docker-compose.prod.yml up -d --force-recreate nginx

# 验证 HTTPS 启动
docker compose -f docker-compose.prod.yml logs nginx | tail -20
curl -I https://ielts.example.com/health   # 应 200
```

如证书路径与 `nginx.conf` 中不一致，先编辑 `nginx/nginx.conf` 的 `ssl_certificate` 行，再重建。

---

## 5. 一键启动（已签发证书后）

首次部署完成证书签发后，后续部署（重启 / 升级 / 迁移）一键即可：

```bash
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
```

启动顺序由 `depends_on` + `condition` 保证：

```text
postgres (wait healthy)
   ↓
db-init (run alembic upgrade head + seed_admin.py, exit 0)
   ↓
backend (wait db-init completed_successfully)
   ↓
nginx (wait backend started)
```

---

## 6. 验证部署

### 6.1 服务状态

```bash
docker compose -f docker-compose.prod.yml ps
```

预期：

| 容器 | 状态 |
| --- | --- |
| `ielts-postgres-prod` | `Up (healthy)` |
| `ielts-db-init-prod` | `Exited 0`（一次性迁移+种子，正常退出） |
| `ielts-backend-prod` | `Up (healthy)` |
| `ielts-nginx-prod` | `Up` |

### 6.2 功能验证

```bash
# 后端健康检查
curl -I https://ielts.example.com/api/v1/health
# 预期：HTTP/2 200

# 用户端 SPA
curl -I https://ielts.example.com/
# 预期：HTTP/2 200，Content-Type: text/html

# 管理后台 SPA
curl -I https://ielts.example.com/admin/
# 预期：HTTP/2 200

# HTTP → HTTPS 重定向
curl -I http://ielts.example.com/
# 预期：HTTP/1.1 301 Moved Permanently，Location: https://...

# 管理员登录（用 .env.production 中的 SEED_ADMIN_EMAIL / PASSWORD）
curl -X POST https://ielts.example.com/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@ielts.example.com","password":"<your-password>"}'
# 预期：{"code":0,"message":"ok","data":{"access_token":"...","user":{...}}}
```

### 6.3 浏览器验收

按 `AI_CONTEXT.md §3.1 [待办-用户]` 清单逐项验证：

1. 访问 `https://ielts.example.com/` → 用户端首页（未登录落地页）。
2. 注册 / 登录普通用户 → 题库浏览 / 收藏 / 详情。
3. 开始练习 → 创建会话 → 录音上传 → 回放 → 完成会话。
4. 学习数据页 → 概览 / 趋势 / 分布渲染正常。
5. 访问 `https://ielts.example.com/admin/` → 管理员登录 → 录入题目 / 启停。
6. 首页推荐列表 5 级 reason 标签渲染正确。

---

## 7. 管理员初始化（seed_admin）

### 7.1 自动初始化（推荐）

`docker-compose.prod.yml` 中的 `db-init` 服务会在首次 `up` 时自动执行：

```bash
uv run alembic upgrade head
uv run python scripts/seed_admin.py
```

`seed_admin.py` 行为（对齐 database-design §9.3 / §9.4）：

- 从环境变量读取 `SEED_ADMIN_EMAIL` / `SEED_ADMIN_PASSWORD` / `SEED_ADMIN_NICKNAME`。
- **幂等**：已存在 active 管理员则跳过，不报错。
- **生产密码强度校验**：`APP_ENV=production` 时强制密码 ≥ 12 位且含字母+数字，不通过则 `sys.exit`。
- 凭证 **绝不写入代码库**，不回显密码。
- 依赖迁移 017（roles 表含 `admin` 角色）。

### 7.2 手动重新初始化（如忘记密码 / 需新增管理员）

如 db-init 已跑过但需重置管理员密码，**不要重跑 db-init**（会因幂等跳过）。改用以下方式：

#### 方式 1：进 backend 容器执行脚本

```bash
# 进入 backend 容器
docker compose -f docker-compose.prod.yml exec backend sh

# 在容器内（带 .env.production 环境变量）
# 修改 SEED_ADMIN_EMAIL 指向新邮箱，或先在数据库删旧管理员记录
uv run python -m scripts.seed_admin
exit
```

#### 方式 2：直接 SQL 重置密码（推荐，无需改环境变量）

在 backend 容器内用 Python 生成新密码哈希：

```bash
docker compose -f docker-compose.prod.yml exec backend python -c \
  "from app.core.security import hash_password; print(hash_password('NEW_PASSWORD_HERE'))"
# 复制输出的 hash

# 进 postgres 容器更新
docker compose -f docker-compose.prod.yml exec postgres psql -U ielts -d ielts_speaking -c \
  "UPDATE users SET password_hash='<复制的hash>' WHERE email='admin@ielts.example.com';"
```

> `hash_password` 使用 bcrypt cost=12（对齐 `core/security.py`），生成的 hash 已含 salt，可直接写入。

### 7.3 验证管理员账号

```bash
# 登录测试
curl -X POST https://ielts.example.com/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@ielts.example.com","password":"<your-password>"}'

# 预期返回的 user.role 为 "admin"
```

---

## 8. 证书续签

Let's Encrypt 证书有效期 90 天，需定期续签。

### 8.1 自动续签（推荐）

在 VPS 宿主机配置 cron：

```bash
sudo crontab -e
```

添加（每天凌晨 3 点检查，certbot 仅在到期前 30 天实际续签）：

```cron
0 3 * * * certbot renew --quiet --deploy-hook "docker compose -f /path/to/ielts-speaking/docker-compose.prod.yml restart nginx"
```

`--deploy-hook` 仅在证书实际更新后执行，重启 nginx 加载新证书。

### 8.2 手动续签

```bash
sudo certbot renew
# 如有更新，重启 nginx
docker compose -f docker-compose.prod.yml restart nginx
```

### 8.3 验证续签

```bash
sudo certbot certificates
# 查看有效期
echo | openssl s_client -connect ielts.example.com:443 2>/dev/null | openssl x509 -noout -dates
```

---

## 9. 日常运维

### 9.1 查看日志

```bash
# 全部服务
docker compose -f docker-compose.prod.yml logs -f --tail=100

# 单服务
docker compose -f docker-compose.prod.yml logs -f backend
docker compose -f docker-compose.prod.yml logs -f nginx
docker compose -f docker-compose.prod.yml logs -f postgres
```

### 9.2 重启服务

```bash
# 单服务
docker compose -f docker-compose.prod.yml restart backend

# 全部
docker compose -f docker-compose.prod.yml restart
```

### 9.3 升级代码

```bash
cd /path/to/ielts-speaking
git pull origin main
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
# --build 重建受影响镜像；db-init 会重跑迁移（幂等）
```

### 9.4 备份

#### 数据库备份

```bash
# 一次性备份
docker compose -f docker-compose.prod.yml exec postgres pg_dump -U ielts ielts_speaking | gzip > backup_$(date +%Y%m%d).sql.gz

# 恢复
gunzip -c backup_YYYYMMDD.sql.gz | docker compose -f docker-compose.prod.yml exec -T postgres psql -U ielts ielts_speaking
```

#### 录音文件备份

录音存储在 `backend-storage-prod` 卷，需连同 DB 一起备份：

```bash
# 备份录音卷
docker run --rm -v backend-storage-prod:/data -v $(pwd):/backup alpine \
  tar czf /backup/recordings_$(date +%Y%m%d).tar.gz -C /data .

# 恢复
docker run --rm -v backend-storage-prod:/data -v $(pwd):/backup alpine \
  tar xzf /backup/recordings_YYYYMMDD.tar.gz -C /data
```

> **建议**：配置 cron 定时备份到对象存储（如 S3 / OSS）或异地服务器，DB + 录音一起备份。

### 9.5 清理（谨慎）

```bash
# 清理未使用镜像（释放磁盘）
docker image prune -f

# ⚠ 切勿在生产运行 docker compose down -v，-v 会删除持久化卷（含 DB + 录音）
```

---

## 10. 故障排查

### 10.1 nginx 启动失败：找不到证书

**症状**：`nginx` 容器日志 `cannot load certificate ... No such file or directory`。

**原因**：首次部署未签发证书就用 HTTPS 配置启动。

**解决**：按 §4 首次部署流程，先用 bootstrap 配置或先签发证书。

### 10.2 db-init 失败：roles 表缺少 admin

**症状**：`[seed_admin] roles 表缺少 'admin' 角色，请先执行 alembic upgrade head`。

**原因**：`alembic upgrade head` 未执行或迁移 017 未应用。

**解决**：

```bash
docker compose -f docker-compose.prod.yml logs db-init   # 查看 alembic 输出
docker compose -f docker-compose.prod.yml exec backend uv run alembic current
# 应为 017；如非，手动 upgrade
docker compose -f docker-compose.prod.yml exec backend uv run alembic upgrade head
```

### 10.3 backend 502 Bad Gateway

**症状**：nginx 返回 502，`/api/v1/health` 不通。

**排查**：

```bash
docker compose -f docker-compose.prod.yml ps backend   # 是否 Up
docker compose -f docker-compose.prod.yml logs backend --tail=50
# 常见：DATABASE_URL 错误 / postgres 未 healthy / 迁移失败
```

### 10.4 录音上传 413 Request Entity Too Large

**症状**：上传录音返回 413。

**原因**：nginx `client_max_body_size` 限制。

**检查**：`nginx/nginx.conf` 中 `/api/` location 已设 `client_max_body_size 60m`（对齐 common.md §6.2 50MB + 余量）。如仍报错，检查是否被其他 server 块覆盖。

### 10.5 HTTPS 证书不生效

**症状**：浏览器提示证书错误 / 不安全。

**排查**：

```bash
sudo certbot certificates                       # 证书是否存在且未过期
docker compose -f docker-compose.prod.yml exec nginx nginx -t   # 配置语法
curl -vI https://ielts.example.com/ 2>&1 | grep -E "subject|issuer|expire"
```

### 10.6 CORS 错误

**症状**：浏览器控制台 `CORS policy` 错误。

**解决**：检查 `.env.production` 的 `CORS_ORIGINS` 是否包含实际访问的 HTTPS 域名。修改后重启 backend：

```bash
docker compose -f docker-compose.prod.yml restart backend
```

---

## 11. 安全清单

部署后逐项确认：

- [ ] `.env.production` 权限 `chmod 600`，仅 owner 可读。
- [ ] `JWT_SECRET` / `POSTGRES_PASSWORD` / `SEED_ADMIN_PASSWORD` 均为强随机值，非默认。
- [ ] `SEED_ADMIN_PASSWORD` 已在生产首次登录后修改（避免环境变量长期泄露）。
- [ ] 防火墙仅放行 22 / 80 / 443，未暴露 5432 / 8000 到公网。
- [ ] Let's Encrypt 自动续签 cron 已配置。
- [ ] DB + 录音卷定时备份已配置，且已验证可恢复。
- [ ] SSH 禁用密码登录，仅用 key。
- [ ] `fail2ban` 或类似已部署（防暴力破解）。
- [ ] `docker compose down -v` 列为禁忌操作（`-v` 删卷）。

---

## 12. 回滚

### 12.1 代码回滚

```bash
cd /path/to/ielts-speaking
git log --oneline -5                  # 找到上一个稳定 commit
git checkout <stable-commit>
docker compose -f docker-compose.prod.yml --env-file .env.production up -d --build
```

> 如新版本含数据库迁移（schema 变更），回滚代码前需先评估迁移是否可逆。Alembic 迁移应配套 `downgrade`，但生产回滚 schema 风险高，优先 **前进式修复**（写新迁移修正问题）。

### 12.2 数据库回滚（谨慎）

```bash
docker compose -f docker-compose.prod.yml exec backend uv run alembic downgrade -1
# 回退一个版本；仅在有 downgrade 路径时可用
```

---

## 13. 附录：服务端口与卷清单

### 13.1 端口

| 服务 | 内部端口 | 外部暴露 | 说明 |
| --- | --- | --- | --- |
| nginx | 80 / 443 | 80 / 443 | 唯一外网入口 |
| backend | 8000 | 无 | 由 nginx 反代 |
| postgres | 5432 | 无 | 仅内部网络 |

### 13.2 Docker 卷

| 卷名 | 挂载点 | 用途 | 备份策略 |
| --- | --- | --- | --- |
| `pgdata-prod` | `/var/lib/postgresql/data` | PostgreSQL 数据 | pg_dump 定时 |
| `backend-storage-prod` | `/app/storage` | 录音文件 | tar 定时 |
| `certbot-webroot` | `/var/www/certbot` | ACME 验证 | 无需备份（可重建） |

### 13.3 关键文件清单

| 文件 | 用途 |
| --- | --- |
| `docker-compose.prod.yml` | 生产服务编排 |
| `.env.production.example` | 环境变量模板（提交到代码库） |
| `.env.production` | 实际环境变量（**不提交**） |
| `backend/Dockerfile` | 后端镜像构建 |
| `nginx/Dockerfile` | Nginx 网关镜像构建（含前端静态资源） |
| `nginx/nginx.conf` | HTTPS 主配置 |
| `nginx/nginx.bootstrap.conf` | 首次部署 HTTP bootstrap 配置 |
| `backend/scripts/seed_admin.py` | 管理员初始化脚本 |

---

## 变更记录

| 版本 | 日期 | 变更 |
| --- | --- | --- |
| v0.1 | 2026-07-24 | 初始创建：首次部署 + HTTPS 签发 + seed_admin + 续签 + 运维 + 故障排查 + 安全清单 + 回滚 |

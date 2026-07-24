# 生产统一 nginx 网关（Phase 12.3，system-architecture §1.2）
# 多阶段构建：node 构建 user-web + admin-web → nginx 托管静态 + 反代 /api + HTTPS
#
# 路由策略（单域名路径分发）：
#   /          → user-web SPA（用户端）
#   /admin/    → admin-web SPA（管理后台，base=/admin/）
#   /api/      → backend:8000（FastAPI）
#   /.well-known/acme-challenge/ → Certbot 证书签发（HTTP 80）
#
# HTTPS：443 由 nginx 终止，证书挂载自宿主机 /etc/letsencrypt
FROM node:22-alpine AS build
RUN corepack enable && corepack prepare pnpm@10.28.1 --activate
WORKDIR /app

# 依赖层（先复制 workspace 配置 + 共享包 + 两个 app，pnpm workspace 需全部就位）
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml ./
COPY packages ./packages
COPY apps/user-web ./apps/user-web
COPY apps/admin-web ./apps/admin-web
RUN pnpm install --frozen-lockfile

# user-web 构建（base='/'，根路径）
RUN pnpm --filter @ielts/user-web build

# admin-web 构建（base='/admin/'，子路径，生产统一部署）
# ADMIN_BASE 环境变量注入 vite.config.ts base，使静态资源引用 /admin/assets/...
ENV ADMIN_BASE=/admin/
RUN pnpm --filter @ielts/admin-web build

# ---------------------------------------------------------------------------
# 运行阶段：nginx 托管两套静态文件 + 反代 /api + HTTPS
# ---------------------------------------------------------------------------
FROM nginx:alpine AS runtime

# 移除默认配置，使用统一网关配置
RUN rm /etc/nginx/conf.d/default.conf

# user-web 静态文件 → /usr/share/nginx/user-web
# admin-web 静态文件 → /usr/share/nginx/admin-web
COPY --from=build /app/apps/user-web/dist /usr/share/nginx/user-web
COPY --from=build /app/apps/admin-web/dist /usr/share/nginx/admin-web

# 统一网关 nginx 配置（HTTPS 主配置 + bootstrap HTTP 配置）
COPY nginx/nginx.conf /etc/nginx/conf.d/nginx.conf
COPY nginx/nginx.bootstrap.conf /etc/nginx/conf.d/nginx.bootstrap.conf
# 默认启用 HTTPS 主配置；首次部署缺证书时换 bootstrap（见 deploy.md）
RUN mv /etc/nginx/conf.d/nginx.conf /etc/nginx/conf.d/default.conf

# Certbot 证书续签 webroot 目录（acme-challenge）
RUN mkdir -p /var/www/certbot

EXPOSE 80 443

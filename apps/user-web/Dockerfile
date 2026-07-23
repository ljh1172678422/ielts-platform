# 用户端 SPA：多阶段构建（node 构建 → nginx 托管）
# 对齐 system-architecture §1.2：user-web 构建为静态文件，nginx 托管 + /api 反代
FROM node:22-alpine AS build
RUN corepack enable && corepack prepare pnpm@10.28.1 --activate
WORKDIR /app

# 依赖层（先复制 workspace 配置与共享包，利用缓存）
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml ./
COPY packages ./packages
COPY apps/user-web ./apps/user-web
RUN pnpm install --frozen-lockfile

# 构建
RUN pnpm --filter @ielts/user-web build

# 运行阶段：nginx 托管静态文件 + 反代 /api 到 backend
FROM nginx:alpine AS runtime
COPY --from=build /app/apps/user-web/dist /usr/share/nginx/html
COPY apps/user-web/nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80

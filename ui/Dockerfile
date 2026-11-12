# syntax=docker/dockerfile:1
ARG NODE_VERSION=24.22.1

################
# Dependencies #
################
# Keep in step with node and pnpm in mise.toml
FROM node:${NODE_VERSION}-bookworm-slim AS deps
RUN npm install --global pnpm@11.28.7
WORKDIR /app
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml /app/
RUN --mount=type=cache,id=pnpm,target=/pnpm/store \
    pnpm install --frozen-lockfile --store-dir /pnpm/store


######################
# Development (Tilt) #
######################
# Vite serves the source through Traefik; Tilt syncs /app/src
FROM deps AS dev
COPY . /app/
ARG VITE_THEME=default
ENV VITE_THEME=$VITE_THEME
# V8 sizes its heap from the host's memory, not the container's limit
ENV NODE_OPTIONS=--max-old-space-size=1024
# Vite writes its cache and the generated route tree, and Tilt syncs as this user
RUN chown -R node:node /app
USER node
EXPOSE 8080
CMD ["./node_modules/.bin/vite", "--host", "--port", "8080"]


#########
# Build #
#########
FROM deps AS build
COPY . /app/
ARG VITE_THEME=default
ENV VITE_THEME=$VITE_THEME
RUN pnpm vite build


##############
# Production #
##############
FROM nginxinc/nginx-unprivileged:stable AS production
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

# syntax=docker/dockerfile:1
ARG PYTHON_VERSION=3.14.8

##########################################
# Build the venv with a standalone Python #
##########################################
# Distroless is glibc based, so build on the matching Debian release with a
# uv-managed standalone Python that can be copied into the runtime image as-is
FROM debian:trixie-slim AS build
ARG PYTHON_VERSION
ENV \
  UV_PYTHON=${PYTHON_VERSION} \
  UV_PYTHON_INSTALL_DIR=/python \
  UV_PYTHON_PREFERENCE=only-managed \
  UV_PROJECT_ENVIRONMENT=/.venv \
  UV_COMPILE_BYTECODE=1 \
  UV_LINK_MODE=copy
# Keep in step with uv in mise.toml
COPY --from=ghcr.io/astral-sh/uv:0.12.24 /uv /usr/local/bin/
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates tini \
    && rm -rf /var/lib/apt/lists/* \
    && uv python install "$PYTHON_VERSION"
WORKDIR /app
# Dependencies first, to cache them in a docker layer
COPY ./uv.lock ./pyproject.toml ./README.md ./LICENSE.txt /app/
COPY ./src/lib_opendefence_core/pyproject.toml ./src/lib_opendefence_core/README.md ./src/lib_opendefence_core/LICENSE.txt /app/src/lib_opendefence_core/
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev --all-extras --no-install-workspace
# The package itself, non-editable so /app is not needed at runtime
COPY ./src /app/src/
RUN --mount=type=cache,target=/root/.cache/uv uv sync --locked --no-dev --all-extras --no-editable
# Drop what a non-interactive runtime never uses. The python binary links
# libpython statically, so the shared library is only needed for embedding.
RUN cd /python/cpython-*/ \
    && rm -rf \
        bin/idle* bin/pip* bin/pydoc* bin/*-config \
        include share \
        lib/libpython* lib/libtcl* lib/pkgconfig lib/itcl* lib/tcl* lib/tk* lib/thread* \
        lib/python3.14/ensurepip lib/python3.14/idlelib lib/python3.14/pydoc_data \
        lib/python3.14/tkinter lib/python3.14/turtledemo lib/python3.14/turtle.py \
        lib/python3.14/site-packages/pip lib/python3.14/site-packages/pip-*


#######################
# Development (Tilt) #
#######################
# Same runtime with busybox (Tilt's live update needs tar). Source synced to
# /app/src shadows the installed package via PYTHONPATH.
FROM gcr.io/distroless/cc-debian13:debug AS dev
ENV \
  LANG=C.UTF-8 \
  PATH="/.venv/bin:$PATH" \
  PYTHONPATH=/app/src
COPY --from=build /usr/bin/tini-static /sbin/tini
COPY --from=build /python /python
COPY --from=build /.venv /.venv
COPY --chown=65532:65532 ./src /app/src/
WORKDIR /app
# Deployments pass the subcommand as args: `api run` or `operator run`
ENTRYPOINT ["/sbin/tini", "--", "opendefence_core"]
CMD ["--help"]


##############
# Production #
##############
FROM gcr.io/distroless/cc-debian13 AS production
ENV \
  LANG=C.UTF-8 \
  PATH="/.venv/bin:$PATH"
COPY --from=build /usr/bin/tini-static /sbin/tini
COPY --from=build /python /python
COPY --from=build /.venv /.venv
WORKDIR /app
# Deployments pass the subcommand as args: `api run` or `operator run`
ENTRYPOINT ["/sbin/tini", "--", "opendefence_core"]
CMD ["--help"]

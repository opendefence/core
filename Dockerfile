# syntax=docker/dockerfile:1
##########################################
# Build the venv with a standalone Python #
##########################################
# Distroless is glibc based, so build on the matching Debian release with a
# uv-managed standalone Python that can be copied into the runtime image as-is
FROM debian:trixie-slim AS build
ENV \
  UV_PYTHON_INSTALL_DIR=/python \
  UV_PYTHON_PREFERENCE=only-managed \
  UV_PROJECT_ENVIRONMENT=/.venv \
  UV_COMPILE_BYTECODE=1 \
  UV_LINK_MODE=copy
COPY --from=ghcr.io/astral-sh/uv:0.12.13 /uv /usr/local/bin/
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        git \
        openssh-client \
        tini \
    && rm -rf /var/lib/apt/lists/* \
    # Host keys for git+ssh dependencies (used with --mount=type=ssh)
    && mkdir -p -m 0700 ~/.ssh && ssh-keyscan gitlab.com github.com | sort > ~/.ssh/known_hosts \
    && uv python install 3.14
WORKDIR /app
# Dependencies first, to cache them in a docker layer
COPY ./uv.lock ./pyproject.toml ./README.md /app/
RUN --mount=type=ssh uv sync --locked --no-dev --all-extras --no-install-project
# The package itself, non-editable so /app is not needed at runtime
COPY ./src /app/src/
RUN --mount=type=ssh uv sync --locked --no-dev --all-extras --no-editable
# Drop what a non-interactive runtime never uses. The python binary links
# libpython statically, so the shared library is only needed for embedding.
RUN cd /python/cpython-3.14.*/ \
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
ENTRYPOINT ["/sbin/tini", "--"]
CMD ["opendefence_core"]


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
ENTRYPOINT ["/sbin/tini", "--"]
CMD ["opendefence_core"]

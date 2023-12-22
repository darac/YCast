# syntax=docker/dockerfile:1
# Keep this syntax directive! It's used to enable Docker BuildKit

################################
# PYTHON-BASE
# Sets up all our shared environment variables
################################
FROM python:3.11-slim AS python-base

# Setup env
ENV PYTHONUNBUFFERED=1 \
    # pip
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PIP_DEFAULT_TIMEOUT=100 \
    \
    # Poetry
    # https://python-poetry.org/docs/configuration/#using-environment-variables
    POETRY_VERSION=1.7.1 \
    # make poetry install to this location
    POETRY_HOME="/opt/poetry" \
    # do not ask any interactive question
    POETRY_NO_INTERACTION=1 \
    # never create virtual environment automaticly, only use env prepared by us
    POETRY_VIRTUALENVS_CREATE=false \
    \
    # this is where our requirements + virtual environment will live
    VIRTUAL_ENV="/venv" \
    \
    LANG=C.UTF.8 \
    LC_ALL=C.UTF-8

# prepend poetry and venv to path
ENV PATH="$POETRY_HOME/bin:$VIRTUAL_ENV/bin:$PATH"

RUN python -m venv ${VIRTUAL_ENV}

WORKDIR /app
ENV PYTHONPATH="/app:$PYTHONPATH"

################################
# BUILDER-BASE
# Used to build deps + create our virtual environment
################################
FROM python-base AS builder-base

RUN rm -f /etc/apt/apt.conf.d/docker-clean; \
    echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' \
    > /etc/apt/apt.conf.d/keep-cache
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && \
    apt-get install -y --no-install-recommends \
    apt-transport-https \
    ca-certificates \
    curl \
    git \
    gnupg \
    nano

# install poetry - respects $POETRY_VERSION & $POETRY_HOME
# The --mount will mount the buildx cache directory to where
# Poetry and Pip store their cache so that they can re-use it
RUN --mount=type=cache,target=/root/.cache \
    curl -sSL https://install.python-poetry.org | python -

# used to init dependencies
WORKDIR /app
COPY poetry.lock pyproject.toml ./
# install runtime deps to $VIRTUAL_ENV
RUN --mount=type=cache,target=/root/.cache \
    poetry install --no-root --only main

################################
# PRODUCTION
# Final image used for runtime
################################
FROM python-base AS poetry

RUN rm -f /etc/apt/apt.conf.d/docker-clean; \
    echo 'Binary::apt::APT::Keep-Downloaded-Packages "true";' \
    > /etc/apt/apt.conf.d/keep-cache
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    --mount=type=cache,target=/var/lib/apt,sharing=locked \
    apt-get update && \
    apt-get install -y --no-install-recommends \
    ca-certificates && \
    apt-get clean

# copy in our built poetry + venv
COPY --from=builder-base $POETRY_HOME $POETRY_HOME
COPY --from=builder-base $VIRTUAL_ENV $VIRTUAL_ENV

WORKDIR /app
COPY poetry.lock pyproject ./
COPY ycast ycast/
COPY LICENSE.txt README.md bootstrap.sh ./

#
# Variables
# YC_VERSION version of ycast software
# YC_STATIONS path an name of the indiviudual stations.yml e.g. /ycast/stations/stations.yml
# YC_DEBUG turn ON or OFF debug output of ycast server else only start /bin/sh
# YC_PORT port ycast server listens to, e.g. 80
#
ENV YC_VERSION master
ENV YC_STATIONS /opt/ycast/stations.yml
ENV YC_DEBUG OFF
ENV YC_PORT 80

# Install the app itself
RUN --mount=type=cache,target=/root/.cache \
    poetry install --only=main

#
# Docker Container should be listening for AVR on port 80
#
EXPOSE ${YC_PORT}/tcp

# Run the executable
ENTRYPOINT [ "/app/bootstrap.sh" ]

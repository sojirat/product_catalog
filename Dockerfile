FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

WORKDIR /app

# make: to reuse the existing Makefile targets (make run / make export / ...)
# default-mysql-client: mysqladmin/mysql CLI, handy for debugging and mysqldump
RUN apt-get update \
    && apt-get install -y --no-install-recommends make default-mysql-client \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./requirements.txt

# requirements.txt only covers run_all.py/export_template_mapping.py.
# po_grouper.py additionally needs pandas/numpy/requests, so install them too.
RUN pip install --no-cache-dir -r requirements.txt pandas numpy requests

# The Makefile hardcodes VENV := .venv and calls .venv/bin/python directly, so
# `make run` / `make export` / ... work unchanged both on a host venv and here
# in the container. --system-site-packages lets this venv reuse the packages
# already pip-installed above instead of reinstalling them.
RUN python -m venv .venv --system-site-packages

COPY . .

CMD ["bash"]

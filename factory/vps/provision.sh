#!/usr/bin/env bash
# HUMAN installation step only. Not executed during the no-code-run implementation task.
set -euo pipefail
[ "$(id -u)" = 0 ] || { echo "root gerekli"; exit 1; }
command -v uv >/dev/null || { echo "uv önce resmi dağıtımdan kurulmalı"; exit 1; }
export UV_PYTHON_INSTALL_DIR=/opt/kepler/python UV_PROJECT_ENVIRONMENT=/opt/kepler/venv
cd /srv/kepler
uv sync --frozen --python 3.12
uv venv /opt/kepler/modal --python 3.12
uv pip install --python /opt/kepler/modal/bin/python 'modal[api-proxy-support]==1.6.1'
chown -R root:root /opt/kepler
chmod -R go-w /opt/kepler
echo "Python/Modal ortamları kilitli; servisler başlatılmadı."

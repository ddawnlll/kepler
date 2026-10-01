#!/usr/bin/env bash
# Sunucuda (VPS / Lightning Studio) Hermes + Telegram geçidi kurulumu. Gizli değerler ortamdan gelir, repoya girmez.
# Kullanım: TELEGRAM_BOT_TOKEN=... TELEGRAM_ALLOWED_USERS=<sayısal id> [MODAL_TOKEN_ID=... MODAL_TOKEN_SECRET=...] \
#           [REPO_URL=https://<token>@github.com/ddawnlll/kepler.git] bash factory/setup_hermes.sh
# Doğrulanmadı: resmî dokümandan yazıldı, hiç koşulmadı. İlk koşuda hataları düzelt.
set -euo pipefail
: "${TELEGRAM_BOT_TOKEN:?BotFather token gerekli}" "${TELEGRAM_ALLOWED_USERS:?kendi sayısal Telegram id gerekli}"

command -v hermes >/dev/null || curl -fsSL https://hermes-agent.nousresearch.com/install.sh | bash
export PATH="$HOME/.local/bin:$PATH"

mkdir -p ~/.hermes && umask 077
{ grep -v '^TELEGRAM_' ~/.hermes/.env 2>/dev/null || true
  echo "TELEGRAM_BOT_TOKEN=$TELEGRAM_BOT_TOKEN"
  echo "TELEGRAM_ALLOWED_USERS=$TELEGRAM_ALLOWED_USERS"; } > ~/.hermes/.env.new
mv ~/.hermes/.env.new ~/.hermes/.env && chmod 600 ~/.hermes/.env

command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | sh
if [ -n "${REPO_URL:-}" ] && [ ! -d ~/kepler ]; then git clone "$REPO_URL" ~/kepler; fi
if [ -n "${MODAL_TOKEN_ID:-}" ]; then uv tool run modal token set --token-id "$MODAL_TOKEN_ID" --token-secret "$MODAL_TOKEN_SECRET"; fi

echo "Sağlayıcı/model seçimi etkileşimlidir: 'hermes model' (ChatGPT Plus OAuth için openai-codex). Sonra:"
if command -v systemctl >/dev/null && systemctl --user status >/dev/null 2>&1; then hermes gateway install
else tmux new-session -d -s hermes "hermes gateway" && echo "geçit tmux 'hermes' oturumunda"; fi

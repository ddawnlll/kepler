#!/usr/bin/env bash
# VPS kurulumu, WP6 (docs/factory.md §5, §16): ayrılmış OS kullanıcıları, dizinler, bare repo + hook, sudoers ve servis dosyaları. Root ile.
# Gizli değer almaz ve yazmaz. Kullanım: sudo bash setup.sh   (bu dizinden)
# Bu betik uv/Python ortamını (krunner) ve Hermes'i kurmaz: o adımlar docs/factory.md §19.1'de.
set -euo pipefail
cd "$(dirname "$0")"
[ "$(id -u)" = 0 ] || { echo "root gerekli"; exit 1; }

# sudoers önce geçici dosyada doğrulanır; bozuk dosya /etc/sudoers.d'ye hiç girmez
visudo -cf sudoers.kepler

# 1. kullanıcılar: jj (insan, sudo), kagent (ajanlar), krunner (ölçüm).
for u in jj kagent krunner kworker kcompute; do id "$u" >/dev/null 2>&1 || useradd -m -s /bin/bash "$u"; chmod 700 "/home/$u"; done
getent group kepler-ipc >/dev/null || groupadd kepler-ipc
getent group kepler-results >/dev/null || groupadd kepler-results
for u in jj kagent krunner; do usermod -aG kepler-ipc "$u"; done
usermod -aG kepler-results krunner
usermod -aG sudo jj
# jj'ye admin'in public anahtarı: yalnızca jj'de yoksa (var olan anahtarlar ezilmez)
install -d -m 700 -o jj -g jj /home/jj/.ssh
[ -s /home/jj/.ssh/authorized_keys ] || install -m 600 -o jj -g jj /home/admin/.ssh/authorized_keys /home/jj/.ssh/authorized_keys
loginctl enable-linger kagent krunner   # systemd --user ve Hermes geçidi oturumsuz yaşasın

# 2. mühür alanı: yalnızca jj. (Gerçek mühür verisi/anahtarı bu betikle gelmez; jj kendisi koyar.)
install -d -m 700 -o jj -g jj /home/jj/kepler-seal

# 3. dizinler: ölçüm /srv/kepler'e, ajanlar /srv/kepler-agent'a sahip; yazma yalnızca sahibe.
install -d -m 755 -o krunner -g krunner /srv/kepler
install -d -m 750 -o kagent -g kagent /srv/kepler-agent
install -d -m 700 -o krunner -g krunner /srv/kepler/state
install -d -m 755 -o root -g root /etc/kepler /usr/local/libexec /opt/kepler /var/lib/kepler-results
if [ -L /etc/kepler/policy.json ] || [ -L /etc/kepler/modal.env ] || [ -L /etc/kepler/telegram.env ]; then
  echo "kepler yapılandırma dosyası symlink olamaz" >&2
  exit 1
fi
[ -e /etc/kepler/policy.json ] || install -m 644 -o root -g root ../policy.json /etc/kepler/policy.json
chown root:root /etc/kepler/policy.json && chmod 644 /etc/kepler/policy.json
for env_file in /etc/kepler/modal.env /etc/kepler/telegram.env; do
  [ -e "$env_file" ] || install -m 600 -o root -g root /dev/null "$env_file"
  chown root:root "$env_file" && chmod 600 "$env_file"
done

# 4. bare repo (GitHub ücretsiz planda dal koruması yok → §5.2 yedek yolu). Sahibi krunner; kagent yalnızca sarmalayıcıyla push eder.
[ -d /srv/kepler.git ] || git init -q --bare -b main /srv/kepler.git
chown -R krunner:krunner /srv/kepler.git
install -m 755 -o krunner -g krunner pre-receive /srv/kepler.git/hooks/pre-receive
install -m 755 -o root -g root kepler-receive-pack /usr/local/sbin/kepler-receive-pack
install -m 755 -o root -g root kepler-set-secret /usr/local/sbin/kepler-set-secret
install -m 755 -o root -g root kepler-configure-secret /usr/local/sbin/kepler-configure-secret
install -m 755 -o root -g root kepler-sandbox kepler-research /usr/local/sbin/
install -m 755 -o root -g root kepler-sandbox-worker kepler-research-worker /usr/local/libexec/
# safe.directory yalnızca kagent'in kendi ayarına (sistem geneline değil: root/jj, krunner'ın repo yapılandırmasına güvenmesin)
sudo -u kagent -H git config --global --replace-all safe.directory /srv/kepler.git
install -m 440 -o root -g root sudoers.kepler /etc/sudoers.d/kepler
visudo -cf /etc/sudoers.d/kepler

# 5. durum zamanlayıcısı (krunner'ın uv ortamı kurulduktan sonra çalışır)
install -m 644 -o root -g root kepler-*.service kepler-*.timer /etc/systemd/system/
systemctl daemon-reload
# No services are started by setup. Provision pinned Python environments, configure DEV-only
# credentials and run the acceptance drill before enabling runtime units. Default control=paused.
echo "Kurulum dosyaları hazır; servis başlatılmadı. docs/factory.md §20 açılış kontrol listesi."

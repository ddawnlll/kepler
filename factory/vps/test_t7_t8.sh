#!/usr/bin/env bash
# docs/factory.md §15.1 T7 (korunan yol) ve T8 (mühür erişimi), VPS'te. sudo yetkili kullanıcıyla: bash test_t7_t8.sh
# Her kontrol PASS/FAIL basar; herhangi bir FAIL'de çıkış kodu 1. T7'nin merge_gate yarısı henüz yok: PENDING basılır ve sayılmaz.
# "Reddedildi" yalnızca çıkış koduna değil, gerçek bir red mesajına da bağlıdır (yoksa ENOENT/yazım hatası da PASS sayılırdı).
set -u
fail=0
OUT=$(mktemp)
ok()  { echo "PASS  $1"; }
bad() { echo "FAIL  $1"; fail=1; }
DENY_RE='[Dd]enied|REDDEDİLDİ|rejected|not allowed|not permitted|may not|password is required|declined|geçersiz|yalnızca'
# expect_denied <ad> <kullanıcı> <komut...>: komut başarısız olmalı VE çıktıda red mesajı bulunmalı
expect_denied() { local n=$1 u=$2; shift 2
  if sudo -u "$u" -H bash -c "$*" >"$OUT" 2>&1; then bad "$n (izin verildi: $(head -c 120 "$OUT"))"
  elif grep -Eq "$DENY_RE" "$OUT"; then ok "$n"
  else bad "$n (reddedildi ama red mesajı yok, başka bir hata olabilir: $(head -c 160 "$OUT"))"; fi; }
expect_ok() { local n=$1 u=$2; shift 2; if sudo -u "$u" -H bash -c "$*" >"$OUT" 2>&1; then ok "$n"; else bad "$n ($(head -c 200 "$OUT"))"; fi; }

AG=/srv/kepler-agent/kepler
sudo -u kagent test -d $AG/.git || { echo "kagent klonu yok: $AG"; exit 2; }
before=$(sudo -u krunner sha256sum /srv/kepler/kepler/referee.py | cut -d' ' -f1)
main_before=$(sudo -u krunner git -C /srv/kepler.git rev-parse main)
[ ${#before} = 64 ] && [ ${#main_before} = 40 ] || { echo "ön koşul başarısız: referee.py özeti veya main sha alınamadı"; exit 2; }
cleanup() {
  sudo -u kagent -H bash -c "cd $AG && git config --global --unset core.hooksPath; git tag -d t7probe; git checkout -q main; git branch -D t7tmp; rm -f ~/.hermes/linktest.env" >/dev/null 2>&1
  sudo -u krunner git -C /srv/kepler.git update-ref -d refs/heads/t7probe >/dev/null 2>&1
  sudo -u jj rm -f /home/jj/kepler-seal/CANARY; rm -f "$OUT"
}
trap cleanup EXIT

echo "== T7: OS yazma reddi"
expect_denied "kagent hakem dosyasına (kepler/referee.py) yazamaz" kagent "echo x >> /srv/kepler/kepler/referee.py"
expect_denied "kagent MISSION.md'ye yazamaz" kagent "echo x >> /srv/kepler/MISSION.md"
expect_denied "kagent /srv/kepler içinde dosya açamaz (registry/state yazma)" kagent "touch /srv/kepler/state/x"
expect_denied "kagent bare repo ref'ini doğrudan yazamaz (hook'u atlama)" kagent "git -C /srv/kepler.git update-ref refs/heads/t7probe $main_before"
expect_denied "kagent pre-receive hook'unu değiştiremez" kagent "echo exit 0 > /srv/kepler.git/hooks/pre-receive"
expect_denied "kagent sarmalayıcıyı değiştiremez" kagent "echo x >> /usr/local/sbin/kepler-receive-pack"
expect_denied "kagent krunner olarak serbest komut çalıştıramaz" kagent "sudo -n -u krunner /bin/sh -c id"
expect_denied "kagent root olamaz" kagent "sudo -n true"
expect_denied "kagent sarmalayıcıyı başka depoyla çalıştıramaz" kagent "sudo -n -u krunner /usr/local/sbin/kepler-receive-pack /srv/kepler"
expect_denied "kagent enqueue.py'yi krunner olarak çalıştıramaz (kural bilerek kapalı)" kagent "sudo -n -u krunner /srv/kepler/factory/enqueue.py"
[ "$(sudo -u krunner sha256sum /srv/kepler/kepler/referee.py | cut -d' ' -f1)" = "$before" ] && ok "referee.py özeti değişmedi" || bad "referee.py DEĞİŞTİ"

echo "== T7: dal yolu (kagent -> sarmalayıcı -> pre-receive)"
sudo -u kagent -H bash -c "cd $AG && git checkout -q -B t7tmp && git commit -q --allow-empty -m t7-probe"   # push'un gerçekten bir şey göndermesi için yeni commit
expect_denied "kagent main'e push edemez" kagent "cd $AG && git push origin HEAD:refs/heads/main"
expect_denied "kagent başka dala (feature/x) push edemez" kagent "cd $AG && git push origin HEAD:refs/heads/feature/x"
expect_denied "kagent tam 'refs/heads/agent' adına push edemez" kagent "cd $AG && git push origin HEAD:refs/heads/agent"
expect_denied "kagent refs/replace/* yazamaz" kagent "cd $AG && git push origin HEAD:refs/replace/$main_before"
expect_denied "kagent refs/notes/* yazamaz" kagent "cd $AG && git push origin HEAD:refs/notes/x"
expect_denied "kagent geçersiz karakterli agent dalı yazamaz (agent/x;y)" kagent "cd $AG && git push origin HEAD:'refs/heads/agent/x;y'"
expect_denied "kagent tag push edemez" kagent "cd $AG && git tag -f t7probe && git push origin refs/tags/t7probe"
expect_denied "kagent main'i silemez" kagent "cd $AG && git push origin :refs/heads/main"
echo "-- saldırı: kagent kendi ~/.gitconfig'ine core.hooksPath=/dev/null koyar (sarmalayıcı ortamı sabitlediği için işe yaramamalı)"
sudo -u kagent -H bash -c "git config --global core.hooksPath /dev/null; chmod 755 ~"
expect_denied "hooksPath=/dev/null ile bile main'e push edemez" kagent "cd $AG && git push origin HEAD:refs/heads/main"
sudo -u kagent -H bash -c "git config --global --unset core.hooksPath; chmod 700 ~"
expect_ok     "kagent agent/* dalına push edebilir" kagent "cd $AG && git push origin HEAD:refs/heads/agent/t7/probe"
expect_ok     "kagent kendi agent/* dalını silebilir" kagent "cd $AG && git push origin :refs/heads/agent/t7/probe"
[ "$(sudo -u krunner git -C /srv/kepler.git rev-parse main)" = "$main_before" ] && ok "main değişmedi" || bad "main DEĞİŞTİ"
echo "PENDING  T7'nin ikinci yarısı: agent dalı korunan yolu (kepler/referee.py) değiştirirse merge_gate reddeder. merge_gate.py (WP4) yok; bu kontrol burada koşamaz."

echo "== T8: mühür erişimi"
SEAL=/home/jj/kepler-seal
sudo -u jj test -d $SEAL || { echo "mühür dizini yok"; exit 2; }
sudo -u jj sh -c "echo CANARY-NOT-REAL-SEAL-DATA > $SEAL/CANARY; chmod 600 $SEAL/CANARY"
for u in kagent krunner; do
  expect_denied "$u mühür dizinini listeleyemez" $u "ls $SEAL"
  expect_denied "$u mühür dosyasını okuyamaz" $u "cat $SEAL/CANARY"
  expect_denied "$u jj ev dizinine giremez" $u "cd /home/jj"
  expect_denied "$u mühür dizinine yazamaz" $u "touch $SEAL/x"
  expect_denied "$u sudo ile jj olamaz" $u "sudo -n -u jj id"
done
expect_denied "kagent krunner ev dizinini okuyamaz (token'lar)" kagent "ls /home/krunner"
expect_denied "krunner kagent ev dizinini okuyamaz (API anahtarları)" krunner "ls /home/kagent"
leak=$(sudo find / -xdev \( -path /home/jj -o -path /proc -o -path /tmp/kvps \) -prune -o \( -iname '*seal*key*' -o -iname 'unseal*' -o -iname 'holdout*' \) -print 2>/dev/null | head -3)
[ -z "$leak" ] && ok "mühür anahtarı/verisi adlı dosya jj dizini dışında yok (yalnızca / bölümü, dosya adına göre)" || bad "jj dışında mühürle ilgili dosya: $leak"

echo "== kepler-set-secret: symlink saldırısı (root, kagent'in yolunu izleyip jj'nin dosyasını sızdırmamalı)"
sudo -u kagent -H ln -sfn $SEAL/CANARY /home/kagent/.hermes/linktest.env
printf 'x-not-a-secret\n' | script -qec "sudo kepler-set-secret kagent .hermes/linktest.env T7_PROBE" /dev/null >"$OUT" 2>&1   # script: set-secret'in okuyacağı /dev/tty için sahte terminal
if sudo -u kagent grep -q T7_PROBE /home/kagent/.hermes/linktest.env 2>/dev/null; then ok "set-secret çalıştı (T7_PROBE yazıldı)"; else bad "set-secret çalışmadı: $(head -c 200 "$OUT")"; fi
if sudo -u kagent grep -q CANARY /home/kagent/.hermes/linktest.env 2>/dev/null; then bad "set-secret CANARY içeriğini kagent'e sızdırdı"; else ok "set-secret symlink üzerinden jj'nin dosyasını sızdırmadı"; fi
[ "$(sudo -u jj cat $SEAL/CANARY)" = "CANARY-NOT-REAL-SEAL-DATA" ] && ok "CANARY dosyası değişmedi" || bad "CANARY dosyası değişti"
if printf 'x\n' | script -qec "sudo kepler-set-secret jj .x V" /dev/null >"$OUT" 2>&1 && ! grep -q 'yalnızca' "$OUT"; then bad "set-secret jj'ye yazmayı reddetmedi"; else grep -q 'yalnızca' "$OUT" && ok "set-secret jj'ye yazmayı reddeder" || bad "set-secret jj reddi beklenen mesajı vermedi: $(head -c 120 "$OUT")"; fi
echo "NOT  T8'in 'mühürlü veri Modal Volume'de yok' kısmı Modal token'ı olmadan doğrulanamaz; burada yalnızca OS izolasyonu sınandı."
[ $fail = 0 ] && echo "SONUÇ: YEŞİL (T7 OS+dal yolu, T8 OS; T7 merge_gate yarısı PENDING)" || echo "SONUÇ: KIRMIZI"
exit $fail

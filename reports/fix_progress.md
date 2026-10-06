# Düzeltme işi: ilerleme günlüğü (ev1_plus_new trade denetimi)

Kaynak görev: kullanıcı mesajı (2026-10-06), kaynak rapor `reports/trade_audit.pdf` + iki bağımsız inceleme. Bu dosya bağlam sıkışırsa devam noktasıdır; sonuç tablosu `reports/audit_fixes.md`.
Kurallar: rakamları script üretir; görülmüş veri = "örneklem içi / post-hoc"; mühür (≥ 2026-04-01) yüklenmez; strateji iyileştirilmez; parametre/eşik/ağırlık araması yok.

## Ortam notları (doğrulanmış)
- Modal çalışıyor (`modal run modal_app.py --cmd ...`, token ortamda). Yerel venv: `/tmp/claude-0/venv312/bin/python` (py3.12 + nautilus + pandas/scipy/matplotlib/reportlab).
- MEXC public `contract/detail` bu oturumda erişilebilir (önceki rapor `account_reality.md` 403 demişti) → gerçek kurallar çekildi.
- Hedef borsa: MISSION "Canlı işlem: MEXC"; araştırma verisi Binance USDT-M.
- `ev1_plus_new` seçim prosedürü yazılı değil (PRESETS: "EV1 aynen + yeni uzmanlara 0,1"; `reports/edge_experts_protocol.md`: hiçbir uzman bu protokolle ensemble'a girmez, kapı geçen yok) → 1.3 atlanacak, gerekçeyle.

## Faz günlüğü
(her faz sonunda doldurulur)

## Koşu ÖNCESİ sabitlenen kararlar (sonuçlara bakılmadan; commit tarihi bu bölümün zamanıdır)
Bunlar ölçüm tanımlarıdır; sonuç görüldükten sonra değiştirilmez. Değişirse "sonradan değişti" diye ayrıca yazılır.
1. **0.3 yakınsama ölçütü** (MEXC kuralları vs yuvarlamasız, aynı sermaye, aynı hedefler): sermaye C "yakınsadı" sayılır ⇔ (a) |net_mexc / net_yuvarlamasız − 1| ≤ %5, (b) |Sharpe_mexc − Sharpe_yuvarlamasız| ≤ 0,10 (sabit sermaye), (c) gönderilemeyen emir niyeti payı ≤ %5. Asgari sermaye = ızgaranın ($1k, $2,5k, $5k, $10k, $25k) en küçük C'si ki C ve ızgaradaki tüm büyük noktalar (a)–(c)'yi sağlar. Ücret/slip 10 + 2 bps (değişmedi), `min_notional` = 0 (MEXC `contract/detail`'de ayrı alan yok; minimum = 1 sözleşme = `minVol`).
2. **1.1 DSR**: N = defterden sayılan (`reports/trade_audit_data/fix/trials/trials.json`): repo defteri, Modal-yalnız gerçek (smoke hariç) ve smoke dahil üç sayı; birincil = repo + Modal-yalnız gerçek. Deneme Sharpe dağılımı (σ_SR) yalnızca deneme düzeyinde günlük serisi bulunan setten (EV1 + 9 uzmanın main/abl/nb'leri, `reports/*_data/primary.json`) hesaplanır; ızgara olarak σ_SR ∈ {havuz, 0,25, 0,5, 1,0} yıllık duyarlılık tablosu da yazılır. Ledger satırlarında Sharpe saklanmadığı için N = 4 775 denemenin Sharpe'ı bilinmiyor: bu kısıt raporda yazılır.
3. **1.2 rotasyon null'u**: ensemble `rotate` (tüm semboller aynı k), B = 300, u_i = `default_rng([0, i]).uniform(0,05; 0,95)` (K1 ile aynı tohum), $1 000, fee 10 + slip 2; istatistikler: brüt PnL p, net PnL p, sabit-sermaye Sharpe p; tek yönlü (1 + #{null ≥ gerçek}) / (B + 1). Blok bootstrap: durağan, ortalama blok 20 gün, B = 2000, tohum 0 (`stats.bootstrap_summary` ile aynı ayar).
4. **1.3**: `ev1_plus_new`'i üreten seçim prosedürü yazılı değil → test atlanır (gerekçe: PRESETS yorumu "EV1 aynen + her yeni uzmana 0,1"; `reports/edge_experts_protocol.md` "hiçbir uzman bu protokolle ensemble'a girmez"; bileşim tek tek sonuçlar görüldükten sonra kuruldu).
5. **2.5 benchmark**: (a) `kepler.signals.tsmom(days=365, every=None)` (aylık, 12 ay; Antonacci; `reports/book_signals.md`'de veriye bakmadan sabit), sembol başına sabit notional = sermaye/9, aynı hakem/Spec; (b) eşit notional al-tut (`robust.buy_hold`, K/9); (c) BTC al-tut (K notional). Beta/alfa: stats.nw_alpha (gecikme 5), getiri = günlük PnL / benchmark brüt notional; alt sepeti = 8 alt'ın (BTC hariç) eşit ağırlıklı günlük fiyat getirisi.
6. **2.6 karşı-olgusallar** (post-hoc, betimsel): long-only = hedef notional max(hedef, 0); short×0,5 = negatif hedefler × 0,5; hakem aynı, `run_book` (deftersiz).
7. **2.4 stop karşı-olgusalı**: eski 12 kural aynen (izleyen/sabit × 1; 1,5; 2; 3; 4; 6 σ); yeni sürüm: (i) dolum gap'e duyarlı (bar stop seviyesinin ötesinde açıldıysa açılış fiyatı), (ii) yeniden giriş (stop sonrası bir sonraki karar zamanında, hedef işareti pozisyon yönüyle aynıysa; boyut = sistemin o andaki gerçek pozisyon profili), yeniden girişte stop sıfırlanır; ek dolumların maliyeti yan başına 6 bps.
8. **1.4 kırılım güven aralığı**: giriş ayına göre küme bootstrap (aylar yeniden örneklenir; B = 2000, tohum 0), ortalama bps/trade için %95 yüzdelik; n < 30 grup "yetersiz" işaretlenir.
9. **2.8**: log-oynaklık Shapley ayrıştırması, 4 faktör (yön karışımı/çeşitlendirme, |F| ölçeği, tampon, payda/equity_scale) = 16 konfigürasyon, fiyat-yalnız günlük PnL; taban = hepsi kapalı; kalan fark ayrı satır.
10. **Alt dönemler**: 2020–21 (2020-04-01 → 2021-12-31), 2022–24, 2025+ (→ 2026-03-31).

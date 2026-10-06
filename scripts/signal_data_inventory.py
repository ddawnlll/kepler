"""Faz 0.3 veri envanteri (yalnızca yoklama; pipeline değil): Binance genel arşivi (S3 listesi) + MEXC / OKX / Hyperliquid genel uçları. Çıktı: reports/signal_diagnostics_data/inventory.json.
Binance fapi, Bybit bu ortamdan coğrafi olarak engelli (451/403): oradaki iddialar 'doğrulanmadı' etiketlidir.  python scripts/signal_data_inventory.py"""
import datetime as dt
import json
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

B = "https://s3-ap-northeast-1.amazonaws.com/data.binance.vision"
NS = {"s": "http://s3.amazonaws.com/doc/2006-03-01/"}


def get(u, data=None):
    req = urllib.request.Request(u, data=data, headers={"User-Agent": "kepler-inventory", "Content-Type": "application/json"})
    return urllib.request.urlopen(req, timeout=30).read()


def ls(prefix, delim="/"):
    keys, pre, marker = [], [], ""
    while True:
        r = ET.fromstring(get(f"{B}?prefix={urllib.parse.quote(prefix)}&delimiter={delim}&max-keys=1000&marker={urllib.parse.quote(marker)}"))
        keys += [k.find("s:Key", NS).text for k in r.findall("s:Contents", NS)]
        pre += [p.find("s:Prefix", NS).text for p in r.findall("s:CommonPrefixes", NS)]
        if r.find("s:IsTruncated", NS).text != "true":
            return keys, pre
        marker = keys[-1] if keys else pre[-1]


def rng(prefix):
    k = [x for x in ls(prefix)[0] if x.endswith(".zip")]
    d = sorted(m.group(1) for x in k for m in [re.search(r"(\d{4}-\d{2}(?:-\d{2})?)\.zip", x)] if m)
    return dict(first=d[0], last=d[-1], files=len(d)) if d else None


def day(ms):
    return dt.datetime.fromtimestamp(int(ms) / 1000, dt.UTC).strftime("%Y-%m-%d")


def js(u, data=None):
    try:
        return json.loads(get(u, data))
    except Exception as e:  # noqa: BLE001
        return dict(error=str(e)[:120])


out = dict(binance_archive={}, mexc={}, okx={}, hyperliquid={})
for sym in ("BTCUSDT", "ETHUSDT", "SOLUSDT", "DOGEUSDT"):
    o = {ds: rng(f"data/futures/um/daily/{ds}/{sym}/") for ds in ("metrics", "bookDepth", "bookTicker", "aggTrades", "trades", "liquidationSnapshot")}
    o.update({f"monthly_{ds}": rng(f"data/futures/um/monthly/{ds}/{sym}/{sub}") for ds, sub in (("premiumIndexKlines", "1h/"), ("indexPriceKlines", "1h/"), ("fundingRate", ""), ("aggTrades", ""), ("trades", ""), ("bookTicker", ""))})
    o["spot_klines_1h"] = rng(f"data/spot/monthly/klines/{sym}/1h/")
    out["binance_archive"][sym] = o
out["binance_archive"]["um_daily_datasets"] = [x.split("/")[-2] for x in ls("data/futures/um/daily/")[1]]
k = js("https://contract.mexc.com/api/v1/contract/kline/BTC_USDT?interval=Min60&start=1590000000&end=1600000000")
d = js("https://contract.mexc.com/api/v1/contract/kline/BTC_USDT?interval=Day1&start=1400000000&end=1700000000")
f = js("https://contract.mexc.com/api/v1/contract/funding_rate/history?symbol=BTC_USDT&page_num=1&page_size=100")
fl = js(f"https://contract.mexc.com/api/v1/contract/funding_rate/history?symbol=BTC_USDT&page_num={f['data']['totalPage']}&page_size=100")
t = js("https://contract.mexc.com/api/v1/contract/ticker?symbol=BTC_USDT")
out["mexc"] = dict(kline_1h_first=day(k["data"]["time"][0] * 1000), kline_1d_first=day(d["data"]["time"][0] * 1000), funding_records=f["data"]["totalCount"], funding_oldest=day(fl["data"]["resultList"][-1]["settleTime"]),
                   ticker_has_open_interest_snapshot="holdVol" in t["data"], note="OI yalnızca anlık (ticker.holdVol); tarihsel OI/likidasyon/long-short uçları bulunamadı (kontrol edilen uçlar: kline, funding_rate/history, ticker, index_price)")
oi = js("https://www.okx.com/api/v5/rubik/stat/contracts/open-interest-volume?ccy=BTC&period=1D")
ls_ = js("https://www.okx.com/api/v5/rubik/stat/contracts/long-short-account-ratio?ccy=BTC&period=1D")
fh = js("https://www.okx.com/api/v5/public/funding-rate-history?instId=BTC-USDT-SWAP&limit=100")
out["okx"] = dict(oi_volume_rows=len(oi["data"]), oi_volume_oldest=day(oi["data"][-1][0]), long_short_rows=len(ls_["data"]), long_short_oldest=day(ls_["data"][-1][0]), funding_history_rows_per_call=len(fh["data"]),
                  funding_history_page_oldest=day(fh["data"][-1]["fundingTime"]), liquidation_orders_endpoint_works=bool(js("https://www.okx.com/api/v5/public/liquidation-orders?instType=SWAP&state=filled&uly=BTC-USDT").get("data")),
                  note="rubik OI/long-short yalnızca son ~180 gün (günlük); likidasyon uç noktası yalnızca yakın zaman; funding geçmişi sayfalı")
h = js("https://api.hyperliquid.xyz/info", json.dumps(dict(type="fundingHistory", coin="BTC", startTime=1577836800000)).encode())
out["hyperliquid"] = dict(funding_history_first=day(h[0]["time"]) if isinstance(h, list) and h else h, note="funding geçmişi 2023-05'ten; OI/likidasyon geçmişi bu yoklamada kontrol edilmedi")
out["unreachable_from_this_environment"] = dict(binance_fapi="451 (restricted location)", bybit="403 (CloudFront country block)", note="Binance fapi openInterestHist / Bybit open-interest geçmiş derinliği: doğrulanmadı")
Path("reports/signal_diagnostics_data").mkdir(parents=True, exist_ok=True)
Path("reports/signal_diagnostics_data/inventory.json").write_text(json.dumps(out, indent=1))
print(json.dumps(out["mexc"]), json.dumps(out["okx"]))

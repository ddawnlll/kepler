"""Durable Telegram delivery. At-least-once: ambiguous HTTP failures can duplicate a message."""
import datetime
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request

from factory import store


def send(text):
    token, chat = os.environ["TELEGRAM_BOT_TOKEN"], os.environ["TELEGRAM_CHAT_ID"]
    body = urllib.parse.urlencode({"chat_id": chat, "text": text, "disable_web_page_preview": "true"}).encode()
    request = urllib.request.Request("https://api.telegram.org/bot" + token + "/sendMessage", data=body)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            result = json.load(response)
    except urllib.error.HTTPError as exc:
        # Never log the request URL: it contains the bot token.
        if exc.code == 429:
            raise RuntimeError("Telegram rate limit") from None
        raise RuntimeError(f"Telegram HTTP {exc.code}") from None
    except (urllib.error.URLError, TimeoutError):
        raise RuntimeError("Telegram bağlantı hatası; teslim belirsiz") from None
    if result.get("ok") is not True:
        raise RuntimeError("Telegram isteği reddetti")
    return str(result["result"]["message_id"])


def flush(con, transport=send, now=None):
    now = time.time() if now is None else now
    # An interrupted 'sending' may have reached Telegram; retry carries the same visible event id.
    con.execute("UPDATE outbox SET state='pending' WHERE state='sending' AND updated<?", (now - 60,))
    rows = con.execute("SELECT * FROM outbox WHERE state='pending' AND next_at<=? ORDER BY updated LIMIT 20", (now,)).fetchall()
    for row in rows:
        with store.transaction(con):
            claimed = con.execute("UPDATE outbox SET state='sending',updated=? WHERE id=? AND state='pending'", (now, row["id"])).rowcount
        if not claimed:
            continue
        try:
            message = transport(row["text"] + "\n[kayıt: " + row["id"] + "]")
        except (RuntimeError, OSError, KeyError) as exc:
            con.execute("UPDATE outbox SET state='pending',attempts=attempts+1,next_at=?,updated=?,error=? WHERE id=?",
                        (now + min(3600, 30 * 2 ** min(row["attempts"], 7)), now, str(exc)[:200], row["id"]))
        else:
            con.execute("UPDATE outbox SET state='sent',message_id=?,updated=?,error=NULL WHERE id=?", (message, now, row["id"]))


def budget(con, config, now=None):
    now = time.time() if now is None else now
    midnight = datetime.datetime.fromtimestamp(now, datetime.timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0).timestamp()
    total = con.execute("SELECT coalesce(sum(cost_usd),0) FROM jobs WHERE started>=?", (midnight,)).fetchone()[0]
    if total >= config["budget_usd_daily"]:
        day = datetime.datetime.fromtimestamp(now, datetime.timezone.utc).strftime("%Y-%m-%d")
        store.notify(con, "budget:" + day, f"Kayıtlı günlük tüketim {total:.2f} USD; uyarı eşiği aşıldı. Kayıtsız tüketim dahil değil.")
    return total


if __name__ == "__main__":
    from factory.policy import load
    with store.connect() as connection:
        budget(connection, load())
        flush(connection)

import requests
import csv
import time
import os
import json
from datetime import datetime
from rich.console import Console
from rich.table import Table

console = Console()

# ─── Load Config ────────────────────────────────────────────
with open("config.json") as f:
    cfg = json.load(f)

TOKEN            = cfg["telegram_token"]
CHAT_ID          = cfg["telegram_chat_id"]
BTC_ALERT_BELOW  = cfg["btc_alert_below"]
CHANGE_THRESHOLD = cfg["change_alert_threshold"]

COINS = {
    "bitcoin":    "BTC",
    "ethereum":   "ETH",
    "solana":     "SOL",
    "binancecoin":"BNB"
}

# ─── Telegram ───────────────────────────────────────────────
def send_telegram(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        requests.post(url, json={
            "chat_id": CHAT_ID,
            "text": message,
            "parse_mode": "Markdown"
        }, timeout=10)
    except Exception as e:
        console.print(f"[red]Telegram error: {e}[/red]")

# ─── Fetch Live Data ────────────────────────────────────────
def get_crypto():
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": ",".join(COINS.keys()),
        "vs_currencies": "usd,kes",
        "include_24hr_change": "true"
    }
    return requests.get(url, params=params, timeout=10).json()

def get_forex():
    data = requests.get("https://open.er-api.com/v6/latest/USD", timeout=10).json()
    return {
        "USD/KES": data["rates"]["KES"],
        "USD/EUR": data["rates"]["EUR"],
        "USD/GBP": data["rates"]["GBP"],
    }

# ─── Save to CSV ────────────────────────────────────────────
def save_to_csv(crypto, forex):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    rows = []
    for coin_id, symbol in COINS.items():
        rows.append({
            "timestamp": timestamp,
            "asset": symbol,
            "price_usd": crypto[coin_id]["usd"],
            "price_kes": crypto[coin_id]["kes"],
            "change_24h": round(crypto[coin_id]["usd_24h_change"], 2)
        })
    for pair, rate in forex.items():
        rows.append({"timestamp": timestamp, "asset": pair,
                     "price_usd": rate, "price_kes": "", "change_24h": ""})

    write_header = not os.path.exists("prices.csv")
    with open("prices.csv", "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["timestamp","asset","price_usd","price_kes","change_24h"])
        if write_header:
            writer.writeheader()
        writer.writerows(rows)

# ─── Moving Averages ────────────────────────────────────────
def get_moving_averages():
    data = {}
    with open("prices.csv", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            asset = row["asset"]
            try:
                price = float(row["price_usd"])
            except (ValueError, TypeError):
                continue
            if asset not in data:
                data[asset] = []
            data[asset].append(price)

    results = {}
    for asset, prices in data.items():
        if len(prices) >= 7:
            ma7  = sum(prices[-7:])  / 7
            ma21 = sum(prices[-21:]) / min(21, len(prices))
            current = prices[-1]
            if ma7 > ma21:
                trend = "📈 Uptrend"
            elif ma7 < ma21:
                trend = "📉 Downtrend"
            else:
                trend = "➡️ Neutral"
            results[asset] = {
                "ma7": ma7,
                "ma21": ma21,
                "current": current,
                "trend": trend
            }
    return results

# ─── Build Telegram Report ──────────────────────────────────
def build_telegram_report(crypto, forex, ma_data):
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = [f"💹 *HexSentinel Market Report*", f"🕐 {now}\n"]

    # Prices
    lines.append("*── LIVE PRICES ──*")
    for coin_id, symbol in COINS.items():
        d = crypto[coin_id]
        change = d["usd_24h_change"]
        arrow = "🟢" if change >= 0 else "🔴"
        lines.append(f"{arrow} *{symbol}*: ${d['usd']:,.2f} (KES {d['kes']:,.0f}) | {change:.2f}%")

    # Forex
    lines.append("\n*── FOREX ──*")
    for pair, rate in forex.items():
        lines.append(f"💱 {pair}: {rate:.4f}")

    # Trend Analysis
    lines.append("\n*── TREND ANALYSIS ──*")
    for asset, ma in ma_data.items():
        if asset in ["BTC", "ETH", "SOL", "BNB"]:
            lines.append(
                f"{ma['trend']} *{asset}*\n"
                f"  MA7: ${ma['ma7']:,.2f} | MA21: ${ma['ma21']:,.2f}"
            )

    # Alerts
    alerts = []
    for coin_id, symbol in COINS.items():
        change = crypto[coin_id]["usd_24h_change"]
        price  = crypto[coin_id]["usd"]
        if change >= CHANGE_THRESHOLD:
            alerts.append(f"🚀 {symbol} UP {change:.2f}% — ${price:,.2f}")
        elif change <= -CHANGE_THRESHOLD:
            alerts.append(f"🔴 {symbol} DOWN {change:.2f}% — ${price:,.2f}")

    if crypto["bitcoin"]["usd"] < BTC_ALERT_BELOW:
        alerts.append(f"⚠️ BTC below ${BTC_ALERT_BELOW:,}!")

    if alerts:
        lines.append("\n*── 🚨 ALERTS ──*")
        lines.extend(alerts)

    return "\n".join(lines)

# ─── Terminal Table ─────────────────────────────────────────
def build_table(crypto, forex):
    table = Table(title=f"💹 HexSentinel Market Tracker — {datetime.now().strftime('%H:%M:%S')}")
    table.add_column("Asset", style="cyan", width=12)
    table.add_column("Price (USD)", justify="right")
    table.add_column("Price (KES)", justify="right", style="yellow")
    table.add_column("24h Change", justify="right")
    table.add_column("Trend", justify="center")

    ma_data = get_moving_averages()

    for coin_id, label in {"bitcoin":"₿ BTC","ethereum":"Ξ ETH","solana":"◎ SOL","binancecoin":"⬡ BNB"}.items():
        d = crypto[coin_id]
        change = d["usd_24h_change"]
        symbol = COINS[coin_id]
        trend = ma_data.get(symbol, {}).get("trend", "—")
        table.add_row(
            label,
            f"${d['usd']:,.2f}",
            f"KES {d['kes']:,.0f}",
            f"{'🟢' if change >= 0 else '🔴'} {change:.2f}%",
            trend
        )
    table.add_section()
    for pair, rate in forex.items():
        table.add_row(pair, f"{rate:.4f}", "—", "—", "—")
    return table

# ─── Main Loop ───────────────────────────────────────────────
def run():
    console.print("\n[bold cyan]💹 HexSentinel Market Tracker v2[/bold cyan]")
    console.print("[dim]Full reports sent to Telegram every 60s.[/dim]\n")
    send_telegram("🟢 *HexSentinel Market Tracker v2 started*\nFull reports with trend analysis incoming every 60s.")

    while True:
        try:
            os.system("clear")
            crypto  = get_crypto()
            forex   = get_forex()
            save_to_csv(crypto, forex)
            ma_data = get_moving_averages()
            report  = build_telegram_report(crypto, forex, ma_data)
            send_telegram(report)
            console.print(build_table(crypto, forex))
            console.print("\n[bold green]📨 Report sent to Telegram[/bold green]")
            console.print("[dim]Next update in 60s... Ctrl+C to stop[/dim]")
            time.sleep(60)
        except KeyboardInterrupt:
            console.print("\n[yellow]Stopped.[/yellow]")
            send_telegram("🔴 *HexSentinel Market Tracker stopped.*")
            break
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            time.sleep(10)

run()

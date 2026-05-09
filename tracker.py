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

TOKEN   = cfg["telegram_token"]
CHAT_ID = cfg["telegram_chat_id"]
BTC_ALERT_BELOW     = cfg["btc_alert_below"]
CHANGE_THRESHOLD    = cfg["change_alert_threshold"]

# ─── Telegram Alert ─────────────────────────────────────────
def send_alert(message):
    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": CHAT_ID, "text": message}, timeout=10)
    except Exception as e:
        console.print(f"[red]Alert failed: {e}[/red]")

# ─── Fetch Crypto ────────────────────────────────────────────
def get_crypto():
    url = "https://api.coingecko.com/api/v3/simple/price"
    params = {
        "ids": "bitcoin,ethereum,solana,binancecoin",
        "vs_currencies": "usd,kes",
        "include_24hr_change": "true"
    }
    return requests.get(url, params=params, timeout=10).json()

# ─── Fetch Forex ─────────────────────────────────────────────
def get_forex():
    data = requests.get("https://open.er-api.com/v6/latest/USD", timeout=10).json()
    return {
        "USD/KES": data["rates"]["KES"],
        "USD/EUR": data["rates"]["EUR"],
        "USD/GBP": data["rates"]["GBP"],
    }

# ─── Save to CSV ─────────────────────────────────────────────
def save_to_csv(crypto, forex):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    coins = {"bitcoin":"BTC","ethereum":"ETH","solana":"SOL","binancecoin":"BNB"}
    rows = []
    for coin_id, symbol in coins.items():
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

# ─── Check Alerts ────────────────────────────────────────────
def check_alerts(crypto):
    alerts = []
    coins = {"bitcoin":"BTC","ethereum":"ETH","solana":"SOL","binancecoin":"BNB"}

    for coin_id, symbol in coins.items():
        change = crypto[coin_id]["usd_24h_change"]
        price  = crypto[coin_id]["usd"]

        if change >= CHANGE_THRESHOLD:
            alerts.append(f"🚀 {symbol} is UP {change:.2f}% in 24h — ${price:,.2f}")
        elif change <= -CHANGE_THRESHOLD:
            alerts.append(f"🔴 {symbol} is DOWN {change:.2f}% in 24h — ${price:,.2f}")

    btc_price = crypto["bitcoin"]["usd"]
    if btc_price < BTC_ALERT_BELOW:
        alerts.append(f"⚠️ BTC BELOW ${BTC_ALERT_BELOW:,} — currently ${btc_price:,.2f}")

    if alerts:
        message = "💹 HexSentinel Market Alert\n\n" + "\n".join(alerts)
        send_alert(message)
        console.print(f"\n[bold yellow]⚡ Alert sent to Telegram![/bold yellow]")

# ─── Build Table ─────────────────────────────────────────────
def build_table(crypto, forex):
    table = Table(title=f"💹 HexSentinel Market Tracker — {datetime.now().strftime('%H:%M:%S')}")
    table.add_column("Asset", style="cyan", width=12)
    table.add_column("Price (USD)", justify="right", style="white")
    table.add_column("Price (KES)", justify="right", style="yellow")
    table.add_column("24h Change", justify="right")

    coins = {"bitcoin":"₿ BTC","ethereum":"Ξ ETH","solana":"◎ SOL","binancecoin":"⬡ BNB"}
    for coin_id, label in coins.items():
        d = crypto[coin_id]
        change = d["usd_24h_change"]
        table.add_row(
            label,
            f"${d['usd']:,.2f}",
            f"KES {d['kes']:,.0f}",
            f"{'🟢' if change >= 0 else '🔴'} {change:.2f}%"
        )
    table.add_section()
    for pair, rate in forex.items():
        table.add_row(pair, f"{rate:.4f}", "—", "—")
    return table

# ─── Main Loop ───────────────────────────────────────────────
def run():
    console.print("\n[bold cyan]💹 HexSentinel Market Tracker[/bold cyan]")
    console.print("[dim]Alerts active. Updates every 60s. Ctrl+C to stop.[/dim]\n")

    send_alert("🟢 HexSentinel Market Tracker started — alerts are active.")

    while True:
        try:
            os.system("clear")
            crypto = get_crypto()
            forex  = get_forex()
            save_to_csv(crypto, forex)
            check_alerts(crypto)
            console.print(build_table(crypto, forex))
            console.print("\n[dim]Next update in 60s... Ctrl+C to stop[/dim]")
            time.sleep(60)
        except KeyboardInterrupt:
            console.print("\n[yellow]Stopped. Data saved to prices.csv[/yellow]")
            send_alert("🔴 HexSentinel Market Tracker stopped.")
            break
        except Exception as e:
            console.print(f"[red]Error: {e}[/red]")
            time.sleep(10)

run()

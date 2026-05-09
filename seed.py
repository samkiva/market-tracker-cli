import requests
import csv
import os
from datetime import datetime, timezone

coins = {
    "bitcoin": "BTC",
    "ethereum": "ETH",
    "solana": "SOL",
    "binancecoin": "BNB"
}

print("🌱 Seeding 30 days of historical data...")

write_header = not os.path.exists("prices.csv")
rows = []

for coin_id, symbol in coins.items():
    url = f"https://api.coingecko.com/api/v3/coins/{coin_id}/market_chart"
    params = {"vs_currency": "usd", "days": "30", "interval": "daily"}
    res = requests.get(url, params=params, timeout=15).json()

    prices = res["prices"]
    for entry in prices:
        timestamp = datetime.fromtimestamp(entry[0]/1000, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        rows.append({
            "timestamp": timestamp,
            "asset": symbol,
            "price_usd": round(entry[1], 2),
            "price_kes": "",
            "change_24h": ""
        })
    print(f"  ✅ {symbol} — {len(prices)} data points loaded")

with open("prices.csv", "w", newline="") as f:
    writer = csv.DictWriter(f, fieldnames=["timestamp","asset","price_usd","price_kes","change_24h"])
    writer.writeheader()
    writer.writerows(rows)

print(f"\n✅ Done — {len(rows)} total rows written to prices.csv")

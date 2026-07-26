#!/usr/bin/env python3
"""
scrape_prices.py
Збирає роздрібні ціни на пальне (А-95, ДП, автогаз) по провідних мережах АЗС
України з index.minfin.com.ua і зберігає результат у prices.json.

Запускається щодня через GitHub Actions (.github/workflows/update-prices.yml).

ВАЖЛИВО ПРО НАДІЙНІСТЬ:
Сайти час від часу міняють верстку. Якщо скрипт почне повертати порожні
або нульові значення — відкрий сторінку мережі в браузері (посилання
нижче в NETWORKS), подивись на реальну HTML-структуру таблиці цін
(права кнопка → "Переглянути код") і онови функцію parse_operator_page()
під нову структуру. Найчастіше ламається саме CSS-селектор таблиці.
"""

import json
import re
import sys
import time
from datetime import datetime, timezone

import requests
from bs4 import BeautifulSoup

# Мережа -> URL сторінки оператора на Мінфін
# Слаги "okko", "ukrnafta", "parallel", "glusco" підтверджені.
# Інші (wog, socar, brsm-nafta, klo, upg, avias) — типові за шаблоном
# сайту, але перед першим запуском варто перевірити вручну, що вони
# відкриваються і ведуть на правильну сторінку.
NETWORKS = {
    "OKKO":         "https://index.minfin.com.ua/ua/markets/fuel/tm/okko/",
    "WOG":          "https://index.minfin.com.ua/ua/markets/fuel/tm/wog/",
    "SOCAR":        "https://index.minfin.com.ua/ua/markets/fuel/tm/socar/",
    "Укрнафта":     "https://index.minfin.com.ua/ua/markets/fuel/tm/ukrnafta/",
    "БРСМ-Нафта":   "https://index.minfin.com.ua/ua/markets/fuel/tm/brsm-nafta/",
    "KLO":          "https://index.minfin.com.ua/ua/markets/fuel/tm/klo/",
    "UPG":          "https://index.minfin.com.ua/ua/markets/fuel/tm/upg/",
    "Parallel":     "https://index.minfin.com.ua/ua/markets/fuel/tm/parallel/",
    "Авіас":        "https://index.minfin.com.ua/ua/markets/fuel/tm/avias/",
    "Glusco":       "https://index.minfin.com.ua/ua/markets/fuel/tm/glusco/",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; FuelPriceTracker/1.0; +personal use)"
}

# Ключові слова, за якими шукаємо потрібний рядок таблиці
FUEL_PATTERNS = {
    "a95": re.compile(r"А[\-\s]?95(?!\+)", re.IGNORECASE),
    "dp":  re.compile(r"(дизел|ДП)", re.IGNORECASE),
    "gas": re.compile(r"(газ|LPG|автогаз)", re.IGNORECASE),
}

PRICE_RE = re.compile(r"\d{2,3}[.,]\d{1,2}")


def fetch(url: str) -> str:
    resp = requests.get(url, headers=HEADERS, timeout=20)
    resp.raise_for_status()
    return resp.text


def parse_operator_page(html: str) -> dict:
    """
    Шукає в HTML таблицю з цінами і повертає {"a95": float|None, "dp": float|None, "gas": float|None}.
    Логіка навмисно "толерантна": йде по всіх рядках таблиць на сторінці,
    шукає рядок, де є назва палива, і бере перше число, схоже на ціну.
    """
    soup = BeautifulSoup(html, "html.parser")
    result = {"a95": None, "dp": None, "gas": None}

    rows = soup.find_all("tr")
    for row in rows:
        text = row.get_text(" ", strip=True)
        for key, pattern in FUEL_PATTERNS.items():
            if result[key] is not None:
                continue
            if pattern.search(text):
                price_match = PRICE_RE.search(text)
                if price_match:
                    value = price_match.group(0).replace(",", ".")
                    try:
                        result[key] = float(value)
                    except ValueError:
                        pass
    return result


def main():
    output = {
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": "index.minfin.com.ua",
        "networks": [],
        "errors": [],
    }

    for name, url in NETWORKS.items():
        try:
            html = fetch(url)
            prices = parse_operator_page(html)
            output["networks"].append({
                "name": name,
                "url": url,
                "a95": prices["a95"],
                "dp": prices["dp"],
                "gas": prices["gas"],
            })
            print(f"OK   {name}: {prices}")
        except Exception as exc:  # noqa: BLE001
            output["errors"].append({"name": name, "error": str(exc)})
            output["networks"].append({
                "name": name, "url": url, "a95": None, "dp": None, "gas": None
            })
            print(f"FAIL {name}: {exc}", file=sys.stderr)

        time.sleep(1.5)  # ввічлива пауза між запитами

    with open("prices.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print("\nЗбережено у prices.json")
    if output["errors"]:
        print(f"Помилок: {len(output['errors'])} — перевір parse_operator_page()", file=sys.stderr)


if __name__ == "__main__":
    main()

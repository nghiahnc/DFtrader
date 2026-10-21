import re
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urljoin, urlparse, parse_qs

import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .common import iso, timestamp

BASE = "https://dfloadout.gg"
SOURCE = BASE + "/cho-dau-gia?category=5&sort=listed-desc"
LOCAL_TZ = timezone(timedelta(hours=7))


class SourceError(ValueError):
    pass


def integer(text):
    text = text.strip().replace("\xa0", " ")
    match = re.fullmatch(r"(?:\d+|\d{1,3}(?:[.,]\d{3})+)(?:\s+đang rao)?", text)
    if not match:
        raise SourceError("Invalid market number")
    return int(re.sub(r"\D", "", text))


def source_time(soup):
    node = soup.select_one("time[datetime]")
    if not node:
        raise SourceError("Missing source timestamp")
    return iso(timestamp(node["datetime"]))


def parse_listing(html):
    soup = BeautifulSoup(html, "html.parser")
    updated = source_time(soup)
    total_match = re.search(r"([\d.,]+)\s+vật phẩm", soup.select_one("time").get_text())
    if not total_match:
        raise SourceError("Missing total count")
    items = []
    for card in soup.select("a.au-card-link"):
        match = re.fullmatch(r"/cho-dau-gia/(\d+)", card.get("href", ""))
        if not match or not all(card.select_one(s) for s in (".au-name", ".au-price", ".au-stock")):
            raise SourceError("Listing structure changed")
        price_text = card.select_one(".au-price").get_text(strip=True)
        stock_text = card.select_one(".au-stock").get_text(strip=True)
        unavailable = price_text == "Chưa có người bán" and stock_text == "Hết hàng"
        price = None if unavailable else integer(price_text)
        if price is not None and price <= 0:
            raise SourceError("Non-positive price")
        items.append({"id": match[1], "name": card.select_one(".au-name").get_text(strip=True),
                      "url": BASE + card["href"], "price": price,
                      "listed": 0 if unavailable else integer(stock_text), "at": updated})
    if not items:
        raise SourceError("Empty market listing")
    pages = {1}
    for link in soup.select('a[href]'):
        query = parse_qs(urlparse(link["href"]).query)
        if query.get("category") == ["5"] and "page" in query:
            pages.add(int(query["page"][0]))
    return items, integer(total_match[1]), max(pages), updated


def parse_detail(html, item):
    soup = BeautifulSoup(html, "html.parser")
    if not soup.select_one("h1.ai-title") or soup.select_one("h1.ai-title").get_text(strip=True) != item["name"]:
        raise SourceError("Detail identity mismatch")
    if abs((timestamp(source_time(soup)) - timestamp(item["at"])).total_seconds()) > 2:
        raise SourceError("Source changed during scan; retry next run")
    price_node = soup.select_one(".ai-price")
    if not price_node or integer(price_node.get_text(strip=True)) != item["price"]:
        raise SourceError("Detail price disagrees with listing")
    rows = soup.select("table tbody tr")
    if not rows:
        raise SourceError("Missing history table")
    history = []
    for row in rows:
        cells = row.select("td")
        if len(cells) != 3:
            raise SourceError("History table changed")
        at = datetime.strptime(cells[0].get_text(strip=True), "%H:%M %d/%m/%y").replace(tzinfo=LOCAL_TZ)
        price, listed = integer(cells[1].get_text(strip=True)), integer(cells[2].get_text(strip=True))
        if price <= 0 or at > timestamp(item["at"]) + timedelta(minutes=1):
            raise SourceError("Invalid history value or future history")
        history.append({"id": item["id"], "at": iso(at), "price": price, "listed": listed})
    # Minute-level source points are retained; analysis samples one point per hour.
    latest = max(history, key=lambda p: p["at"])
    if latest["price"] != item["price"] or latest["listed"] != item["listed"]:
        raise SourceError("Latest history disagrees with listing")
    return history


class Collector:
    def __init__(self, config):
        self.config = config
        self.session = requests.Session()
        self.session.headers["User-Agent"] = "DFTrader/1.0 (personal market price tracker; hourly source)"
        retry = Retry(total=2, backoff_factor=2, status_forcelist=[429, 500, 502, 503, 504], allowed_methods=["GET"])
        self.session.mount("https://", HTTPAdapter(max_retries=retry))
        self.last_request = 0

    def get(self, url):
        time.sleep(max(0, self.config["request_delay_seconds"] - (time.monotonic() - self.last_request)))
        response = self.session.get(url, timeout=(10, 40))
        self.last_request = time.monotonic()
        response.raise_for_status()
        return response.content.decode("utf-8")

    def collect(self, previous=None):
        items, total, pages, updated = parse_listing(self.get(SOURCE))
        if pages > self.config["max_pages"]:
            raise SourceError("Unexpected page count")
        for page in range(2, pages + 1):
            batch, page_total, page_count, page_time = parse_listing(self.get(SOURCE + f"&page={page}"))
            if page_total != total or page_count != pages or page_time != updated:
                raise SourceError("Inconsistent pagination snapshot")
            items.extend(batch)
        if len(items) != total or len({i["id"] for i in items}) != total:
            raise SourceError("Missing or duplicate items")
        if previous:
            old_ids = {i["id"] for i in previous.get("items", [])}
            if len(old_ids) >= 10 and len(items) < len(old_ids) * .9:
                raise SourceError("Unexpected market coverage drop")
        return items, updated

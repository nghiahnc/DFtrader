import math
import statistics
from decimal import Decimal, ROUND_CEILING, ROUND_HALF_UP
from datetime import timedelta

from .common import timestamp


def validate_config(config):
    fee = config["fee"]
    for key in ("sale_rate", "listing_rate"):
        if not isinstance(fee[key], (int, float)) or not math.isfinite(fee[key]) or not 0 <= fee[key] < 1:
            raise ValueError("Fee rates must be fractions from 0 to less than 1")
    if type(fee["confirmed"]) is not bool or not math.isfinite(fee["fixed_per_unit"]) or fee["fixed_per_unit"] < 0:
        raise ValueError("Invalid fee confirmation or fixed fee")
    if fee["sale_rate"] + fee["listing_rate"] >= 1:
        raise ValueError("Combined fee must be less than 100%")
    for value in config["analysis"].values():
        if not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError("Analysis thresholds must be positive")


def hourly(points, at):
    buckets = {}
    for point in sorted(points, key=lambda p: p["at"]):
        instant = timestamp(point["at"])
        if at - timedelta(days=7) <= instant <= at:
            buckets[instant.replace(minute=0, second=0, microsecond=0)] = point
    return list(buckets.values())


def analyze(item, history, config):
    if item["price"] is None:
        return {**item, "status": "unavailable", "median24": None, "median7": None,
                "volatility_pct": None, "discount_pct": None, "trend_pct": None,
                "target": None, "breakeven": None, "net_margin_pct": None, "score": 0,
                "hours24": 0, "hours7": 0, "history": [], "liquidity_verified": False,
                "reasons": ["Nguồn hiện không có người bán. Chưa có cơ sở đánh giá cơ hội."]}
    at = timestamp(item["at"])
    points = hourly(history, at)
    day = [p for p in points if timestamp(p["at"]) >= at - timedelta(hours=24)]
    values = [p["price"] for p in day]
    median24 = statistics.median(values) if values else None
    week_ready = len(points) >= config["analysis"]["min_7d_hours"] and bool(points) and at - timestamp(points[0]["at"]) >= timedelta(days=6)
    median7 = statistics.median(p["price"] for p in points) if week_ready else None
    ready = len(day) >= config["analysis"]["min_hours"] and at - timestamp(day[0]["at"]) >= timedelta(hours=20)
    volatility = statistics.pstdev(values) / statistics.mean(values) * 100 if values else None
    discount = (1 - item["price"] / median24) * 100 if median24 else None
    trend = (statistics.median(values[-6:]) / statistics.median(values[:6]) - 1) * 100 if len(values) >= 12 else None
    # Target is deliberately capped by both historical windows and recent prices.
    target = math.floor(min(median24, median7 or median24, statistics.median(values[-6:]))) if ready else None
    fee = config["fee"]
    net_rate = Decimal(1) - Decimal(str(fee["sale_rate"])) - Decimal(str(fee["listing_rate"]))
    fixed = Decimal(str(fee["fixed_per_unit"]))
    breakeven = int(((Decimal(item["price"]) + fixed) / net_rate).to_integral_value(rounding=ROUND_CEILING)) if fee["confirmed"] else None
    margin = float(((Decimal(target) * net_rate - fixed - item["price"]) / item["price"] * 100).quantize(Decimal('.01'), rounding=ROUND_HALF_UP)) if fee["confirmed"] and target else None
    reasons = []
    status = "observe"
    if not ready:
        status = "insufficient"
        reasons.append("Chưa đủ ít nhất 20 giờ quan sát trong cửa sổ 24 giờ.")
    else:
        reasons.append(f"Giá hiện tại {'thấp' if discount >= 0 else 'cao'} hơn trung vị 24 giờ {abs(discount):.1f}%.")
        if volatility > config["analysis"]["max_volatility_pct"]:
            reasons.append("Biến động vượt ngưỡng theo dõi.")
        elif discount >= config["analysis"]["min_discount_pct"] and trend is not None and trend >= -3 and item["listed"] > 0:
            status = "watch"
            if fee["confirmed"] and margin >= config["analysis"]["min_net_margin_pct"] and week_ready:
                status = "opportunity"
    if not week_ready:
        reasons.append("Chưa đủ độ phủ lịch sử 7 ngày để bật cơ hội sau phí.")
    if not fee["confirmed"]:
        reasons.append("Chưa xác nhận phí bán; chưa tính lãi ròng và chưa bật cảnh báo mua.")
    reasons.append("Chưa xác minh tốc độ bán và nhu cầu thực tế; lượng đang rao là nguồn cung.")
    score = max(0, (discount or 0) - (volatility or 0) * .5 + min(0, trend or 0))
    return {**item, "status": status, "median24": median24, "median7": median7,
            "volatility_pct": round(volatility, 2) if volatility is not None else None,
            "discount_pct": round(discount, 2) if discount is not None else None,
            "trend_pct": round(trend, 2) if trend is not None else None,
            "target": target, "breakeven": breakeven, "net_margin_pct": round(margin, 2) if margin is not None else None,
            "score": round(score, 2), "hours24": len(day), "hours7": len(points),
            "reasons": reasons, "history": points, "liquidity_verified": False}


def make_report(items, history, config, now):
    results = [analyze(item, history.get(item["id"], []), config) for item in items]
    results.sort(key=lambda i: (-i["score"], i["name"]))
    candidates = [i["id"] for i in results if i["status"] in ("watch", "opportunity")][:10]
    from .common import iso
    return {"version": 1, "generated_at": iso(now), "source_updated_at": min(i["at"] for i in items),
            "source_url": "https://dfloadout.gg/cho-dau-gia?category=5&sort=listed-desc",
            "fee_confirmed": config["fee"]["confirmed"], "fee": config["fee"],
            "thresholds": config["analysis"], "candidate_ids": candidates, "items": results,
            "notice": "Giá rao không chứng minh giao dịch khớp. Mục tiêu tham khảo trong 24 giờ, không bảo đảm giá phục hồi hoặc bán được."}

import argparse
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .analysis import make_report, validate_config
from .collector import Collector, SourceError, parse_detail
from .common import iso, read_json, timestamp, write_json


def load_history(root):
    result = {}
    for path in sorted((root / "history").glob("*.json")):
        for point in read_json(path, []):
            result.setdefault(point["id"], []).append(point)
    return result


def save_history(root, history, now, days):
    daily = {}
    cutoff = now - timedelta(days=days)
    for points in history.values():
        unique = { (p["id"], p["at"]): p for p in points if cutoff <= timestamp(p["at"]) <= now }
        for point in unique.values():
            daily.setdefault(point["at"][:10], []).append(point)
    for day, points in daily.items():
        write_json(root / "history" / f"{day}.json", sorted(points, key=lambda p: (p["id"], p["at"])))
    for path in (root / "history").glob("*.json"):
        if path.stem not in daily:
            path.unlink()


def run(root, config, collector=None, now=None):
    now = now or datetime.now(timezone.utc)
    collector = collector or Collector(config["collection"])
    report_path = root / "site" / "data" / "report.json"
    status_path = root / "site" / "data" / "status.json"
    previous = read_json(report_path)
    try:
        validate_config(config)
        items, updated = collector.collect(previous)
        age = (now - timestamp(updated)).total_seconds() / 3600
        if age < -.1 or age > config["analysis"]["max_source_age_hours"]:
            raise SourceError("Source timestamp is stale or in the future")
        history = load_history(root)
        previous_items = {i["id"]: i for i in (previous or {}).get("items", [])}
        for index, item in enumerate(items, 1):
            if item["price"] is None:
                continue
            old = previous_items.get(item["id"])
            if not old or old["at"] != item["at"] or not history.get(item["id"]):
                history.setdefault(item["id"], []).extend(parse_detail(collector.get(item["url"]), item))
                print(f"Validated history {index}/{len(items)}", flush=True)
            elif (old["price"], old["listed"]) != (item["price"], item["listed"]):
                raise SourceError("Market values changed without source timestamp changing")
            history.setdefault(item["id"], []).append({k: item[k] for k in ("id", "at", "price", "listed")})
        report = make_report(items, history, config, now)
        save_history(root, history, now, config["collection"]["retention_days"])
        write_json(report_path, report)
        write_json(status_path, {"ok": True, "attempted_at": iso(now), "last_success_at": iso(now), "error": None})
        print(f"Report ready: {len(items)} items, {len(report['candidate_ids'])} candidates", flush=True)
        return True
    except Exception as exc:
        # Exception bodies may contain URLs/credentials. Public output uses fixed text only.
        response = getattr(exc, "response", None)
        message = "Thu thập thất bại hoặc dữ liệu chưa đạt yêu cầu. Giữ báo cáo thành công gần nhất."
        if response is not None and response.status_code == 403:
            message = "Nguồn đang từ chối truy cập từ máy chủ thu thập (HTTP 403). Hiển thị báo cáo thành công gần nhất; chưa cập nhật tự động được."
        write_json(status_path, {"ok": False, "attempted_at": iso(now),
                                "last_success_at": (previous or {}).get("generated_at"),
                                "error": message,
                                "error_type": type(exc).__name__})
        print(f"Scan failed ({type(exc).__name__}); previous report retained.", file=sys.stderr)
        if response is not None:
            print(f"Source HTTP status: {response.status_code}; challenge: {response.headers.get('cf-mitigated') == 'challenge'}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    sys.exit(0 if run(args.root, read_json(args.root / "config.json")) else 1)


if __name__ == "__main__":
    main()

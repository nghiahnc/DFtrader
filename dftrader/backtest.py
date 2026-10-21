"""Walk-forward paper evaluation. Future observations are used only for outcomes."""
import argparse
from datetime import timedelta
from pathlib import Path

from .analysis import analyze, validate_config
from .common import iso, read_json, timestamp, write_json
from .pipeline import load_history


def evaluate(history, config):
    validate_config(config)
    if not config["fee"]["confirmed"]:
        return {"enabled": False, "reason": "Chưa xác nhận phí bán.", "trades": []}
    trades = []
    for item_id, raw in history.items():
        points = sorted({p["at"]: p for p in raw}.values(), key=lambda p: p["at"])
        next_entry = None
        for index, point in enumerate(points):
            at = timestamp(point["at"])
            if next_entry and at < next_entry:
                continue
            known = points[:index + 1]
            signal = analyze({**point, "name": item_id, "url": ""}, known, config)
            if signal["status"] != "opportunity":
                continue
            deadline = at + timedelta(hours=24)
            future = [p for p in points[index + 1:] if at < timestamp(p["at"]) <= deadline]
            complete = timestamp(points[-1]["at"]) >= deadline
            hits = [p for p in future if p["price"] >= signal["target"]]
            exit_point = hits[0] if hits else (future[-1] if future and complete else None)
            fee = config["fee"]
            exit_price = signal["target"] if hits else (exit_point["price"] if exit_point else None)
            pnl = exit_price * (1 - fee["sale_rate"] - fee["listing_rate"]) - fee["fixed_per_unit"] - point["price"] if exit_price else None
            trades.append({"id": item_id, "entered_at": point["at"], "entry": point["price"], "target": signal["target"],
                           "outcome": "target_observed" if hits else ("expired" if complete else "pending"),
                           "exit_at": exit_point["at"] if exit_point else None,
                           "paper_pnl_per_unit": round(pnl, 2) if pnl is not None else None})
            next_entry = deadline
    return {"enabled": True, "trades": trades,
            "notice": "Mô phỏng theo giá rao, chưa chứng minh có thể mua hoặc khớp lệnh bán. Lãi mô phỏng không phải lãi thực tế."}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path(".local/backtest.json"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    result = evaluate(load_history(root), read_json(root / "config.json"))
    write_json(args.output, result)
    print(f"Paper evaluation: {len(result['trades'])} entries; {args.output}")

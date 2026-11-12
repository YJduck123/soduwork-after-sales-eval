#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""计算签收至申请的连续小时数，并判断是否在政策时限内（含边界）。

用法示例：
    python elapsed_hours.py --signed-at 2026-11-09T10:00:00+08:00 \
        --applied-at 2026-11-12T10:00:00+08:00 --limit-hours 168
退出码：0 计算成功；1 输入非法（缺时区、时间早于签收等）。
"""
import argparse
import json
import sys
from datetime import datetime


def parse_ts(raw):
    text = str(raw).strip()
    if text.endswith("Z") or text.endswith("z"):
        text = text[:-1] + "+00:00"
    moment = datetime.fromisoformat(text)
    if moment.tzinfo is None:
        raise ValueError("时间缺少时区，无法计算连续小时：%s" % raw)
    return moment


def main():
    parser = argparse.ArgumentParser(description="计算签收至申请的连续小时数（含边界）")
    parser.add_argument("--signed-at", required=True, help="签收时间，ISO 8601 且带时区")
    parser.add_argument("--applied-at", required=True, help="申请时间，ISO 8601 且带时区")
    parser.add_argument("--limit-hours", required=True, type=float,
                        help="政策规定的时限小时数，从当次政策读取")
    args = parser.parse_args()

    try:
        signed = parse_ts(args.signed_at)
        applied = parse_ts(args.applied_at)
    except ValueError as exc:
        print(json.dumps({"status": "invalid", "error": str(exc)}, ensure_ascii=False, indent=2))
        return 1

    hours = (applied - signed).total_seconds() / 3600.0
    if hours < 0:
        print(json.dumps({
            "status": "invalid",
            "error": "申请时间早于签收时间，请核对记录",
            "hours": hours
        }, ensure_ascii=False, indent=2))
        return 1

    print(json.dumps({
        "status": "ok",
        "hours": round(hours, 4),
        "limit_hours": args.limit_hours,
        "within_limit": hours <= args.limit_hours,
        "boundary_inclusive": True,
        "signed_at": signed.isoformat(),
        "applied_at": applied.isoformat()
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)

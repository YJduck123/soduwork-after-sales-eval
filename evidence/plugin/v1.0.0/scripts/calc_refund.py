#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按商品行计算建议退款金额：原价总额 - 分摊优惠 - 历史退款。

任一项未知（null/空）时返回 needs_material，不猜金额。
用法示例：
    python calc_refund.py --original 9900 --coupon 1000 --refunded 0
    python calc_refund.py --original 49900 --coupon null --refunded 0
退出码：0 计算成功；2 金额数据不全；1 输入非法或结果为负。
"""
import argparse
import json
import sys


def parse_amount(raw):
    """把命令行参数转为整数分；null/空/未知 返回 None。"""
    if raw is None:
        return None
    text = str(raw).strip().lower()
    if text in {"", "null", "none", "unknown", "nan", "未知"}:
        return None
    try:
        value = int(text)
    except ValueError:
        raise ValueError("金额必须是整数分：%s" % raw)
    if value < 0:
        raise ValueError("金额不能为负数：%d" % value)
    return value


def main():
    parser = argparse.ArgumentParser(description="按商品行计算建议退款金额（单位：分）")
    parser.add_argument("--original", required=True, help="该行原价总额（整数分），未知填 null")
    parser.add_argument("--coupon", required=True, help="该行分摊优惠（整数分），未知填 null")
    parser.add_argument("--refunded", required=True, help="该行历史退款（整数分），未知填 null")
    args = parser.parse_args()

    try:
        original = parse_amount(args.original)
        coupon = parse_amount(args.coupon)
        refunded = parse_amount(args.refunded)
    except ValueError as exc:
        print(json.dumps({"status": "invalid", "refund_cents": None, "error": str(exc)},
                         ensure_ascii=False, indent=2))
        return 1

    missing = [name for name, value in
               (("original", original), ("coupon", coupon), ("refunded", refunded))
               if value is None]
    if missing:
        print(json.dumps({
            "status": "needs_material",
            "refund_cents": None,
            "missing_amounts": missing,
            "formula": None,
            "note": "金额数据不全，整体建议应为补充材料，金额与运费待定"
        }, ensure_ascii=False, indent=2))
        return 2

    refund = original - coupon - refunded
    if refund < 0:
        print(json.dumps({
            "status": "invalid",
            "refund_cents": None,
            "error": "计算结果为负：%d，需核对原价、优惠与历史退款" % refund,
            "formula": "%d - %d - %d" % (original, coupon, refunded)
        }, ensure_ascii=False, indent=2))
        return 1

    print(json.dumps({
        "status": "ok",
        "refund_cents": refund,
        "refund_yuan": "%.2f" % (refund / 100.0),
        "formula": "%d - %d - %d = %d" % (original, coupon, refunded, refund)
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)

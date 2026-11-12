#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""校验售后处理结果，并输出可复算的动作计数。

检查项：
  1. 顶层为数组，case_id 唯一，必填字段齐全，枚举合法；
  2. 动作与 refund_cents / freight 的对应关系；
  3. 待定类不得给出金额，且回复不得承诺运费或金额；
  4. 客户回复不得声称已受理、已退款、已补发、已提交核查等既成事实；
  5. 给出 tickets 时，核对编号集合，并按商品行复算退款金额；
  6. 输出总数、动作分布与待定清单，便于汇总核对。

用法示例：
    python check_results.py --results results.json --tickets tickets.json
    python check_results.py --results results.json --summary-out summary.json
退出码：0 通过；1 存在错误。
"""
import argparse
import json
import re
import sys

ACTION_ENUM = {"退货退款", "直接退款", "补发配件", "补充材料", "物流核查", "人工复核"}
FREIGHT_ENUM = {"商家", "买家", "待定", "不适用"}
PENDING_ACTIONS = {"补充材料", "物流核查", "人工复核"}
REFUND_ACTIONS = {"退货退款", "直接退款"}
REQUIRED_FIELDS = ["case_id", "action", "refund_cents", "freight",
                   "rules", "missing", "reason", "customer_reply"]

CLAIM_PHRASES = ["已按", "已受理", "已退款", "已补发", "已提交", "已发起",
                 "已为您", "已完成", "已安排", "将按", "我们已"]
FREIGHT_PROMISE = re.compile(r"由\s*(商家|买家|您)\s*承担")
MONEY = re.compile(r"(\d+(?:\.\d{1,2})?)\s*(元|分)")

DEFAULT_AMOUNT_FIELDS = ("line_original_cents", "line_coupon_cents", "line_refunded_cents")


def load_json(path):
    with open(path, "r", encoding="utf-8-sig") as handle:
        return json.load(handle)


def reply_amounts(text):
    """抽取回复中的金额，统一换算为分。"""
    values = []
    for number, unit in MONEY.findall(text):
        amount = float(number)
        values.append(int(round(amount * 100)) if unit == "元" else int(round(amount)))
    return values


def check_item(item, errors, warnings):
    case_id = item.get("case_id") if isinstance(item, dict) else None
    label = case_id or "<缺少 case_id>"

    missing_fields = [key for key in REQUIRED_FIELDS if key not in item]
    if missing_fields:
        errors.append("%s 缺少字段：%s" % (label, ", ".join(missing_fields)))
        return

    action = item["action"]
    refund = item["refund_cents"]
    freight = item["freight"]
    reply = item["customer_reply"]

    if action not in ACTION_ENUM:
        errors.append("%s action 非法：%r" % (label, action))
    if freight not in FREIGHT_ENUM:
        errors.append("%s freight 非法：%r" % (label, freight))
    if not isinstance(item["rules"], list):
        errors.append("%s rules 必须是数组" % label)
    if not isinstance(item["missing"], list):
        errors.append("%s missing 必须是数组" % label)
    if not isinstance(item["reason"], str) or not item["reason"].strip():
        errors.append("%s reason 不能为空" % label)
    if not isinstance(reply, str) or not reply.strip():
        errors.append("%s customer_reply 不能为空" % label)
        return

    if action in PENDING_ACTIONS:
        if refund is not None:
            errors.append("%s 待定类动作 refund_cents 必须为 null" % label)
        if freight != "待定":
            errors.append("%s 待定类动作 freight 必须为「待定」" % label)
        if action in {"补充材料", "物流核查"} and not item["missing"]:
            errors.append("%s %s 必须在 missing 中逐项列出缺失材料" % (label, action))
        if FREIGHT_PROMISE.search(reply):
            errors.append("%s 待定状态却在回复中承诺运费承担" % label)
        amounts = reply_amounts(reply)
        if amounts:
            errors.append("%s 待定状态却在回复中出现金额：%s" % (label, amounts))

    if action == "补发配件":
        if refund != 0:
            errors.append("%s 补发配件 refund_cents 必须为 0" % label)
        if freight == "待定":
            errors.append("%s 已确定补发，freight 不应为「待定」" % label)

    if action in REFUND_ACTIONS:
        if not isinstance(refund, int) or isinstance(refund, bool):
            errors.append("%s 退款动作 refund_cents 必须是整数分" % label)
        elif refund < 0:
            errors.append("%s refund_cents 不能为负" % label)
        if freight == "待定":
            errors.append("%s 已确定退款，freight 不应为「待定」" % label)
        if action == "直接退款" and freight in {"商家", "买家"}:
            warnings.append("%s 直接退款通常无需退回，请按政策确认 freight 是否为「不适用」" % label)
        if isinstance(refund, int):
            amounts = reply_amounts(reply)
            if amounts and refund not in amounts:
                errors.append("%s 回复金额 %s 与 refund_cents=%d 不一致" % (label, amounts, refund))

    for phrase in CLAIM_PHRASES:
        if phrase in reply:
            errors.append("%s 回复含既成事实表述「%s」，建议改为建议性措辞" % (label, phrase))


def expected_refund(order, fields):
    values = []
    for name in fields:
        value = order.get(name)
        if value is None:
            return None
        if isinstance(value, bool) or not isinstance(value, int):
            return None
        values.append(value)
    refund = values[0] - values[1] - values[2]
    return refund if refund >= 0 else None


def main():
    parser = argparse.ArgumentParser(description="校验售后处理结果并统计动作分布")
    parser.add_argument("--results", required=True, help="处理结果 JSON 路径")
    parser.add_argument("--tickets", help="输入工单 JSON 路径，用于核对编号与复算金额")
    parser.add_argument("--summary-out", help="可选：把计数摘要写入该 JSON 文件")
    parser.add_argument("--original-field", default=DEFAULT_AMOUNT_FIELDS[0])
    parser.add_argument("--coupon-field", default=DEFAULT_AMOUNT_FIELDS[1])
    parser.add_argument("--refunded-field", default=DEFAULT_AMOUNT_FIELDS[2])
    args = parser.parse_args()

    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    errors, warnings = [], []
    try:
        results = load_json(args.results)
    except (OSError, ValueError) as exc:
        print("FAIL 无法读取结果文件：%s" % exc)
        return 1

    if not isinstance(results, list):
        print("FAIL 结果文件顶层必须是 JSON 数组")
        return 1

    fields = (args.original_field, args.coupon_field, args.refunded_field)
    seen = set()
    counts = {}
    pending_ids = []
    refund_total = 0

    for item in results:
        if not isinstance(item, dict):
            errors.append("数组元素必须是对象")
            continue
        case_id = item.get("case_id")
        if case_id in seen:
            errors.append("case_id 重复：%s" % case_id)
        seen.add(case_id)
        check_item(item, errors, warnings)
        action = item.get("action")
        counts[action] = counts.get(action, 0) + 1
        if action in PENDING_ACTIONS:
            pending_ids.append(case_id)
        if action in REFUND_ACTIONS and isinstance(item.get("refund_cents"), int):
            refund_total += item["refund_cents"]

    if args.tickets:
        try:
            tickets = load_json(args.tickets)
        except (OSError, ValueError) as exc:
            errors.append("无法读取工单文件：%s" % exc)
            tickets = []
        if isinstance(tickets, list):
            ticket_ids = [t.get("case_id") for t in tickets if isinstance(t, dict)]
            if len(ticket_ids) != len(results):
                errors.append("结果条数 %d 与工单条数 %d 不一致" % (len(results), len(ticket_ids)))
            missing_cases = [cid for cid in ticket_ids if cid not in seen]
            extra_cases = [cid for cid in seen if cid not in set(ticket_ids)]
            if missing_cases:
                errors.append("结果缺少工单：%s" % ", ".join(map(str, missing_cases)))
            if extra_cases:
                errors.append("结果多出工单：%s" % ", ".join(map(str, extra_cases)))

            by_id = {item.get("case_id"): item for item in results if isinstance(item, dict)}
            for ticket in tickets:
                if not isinstance(ticket, dict):
                    continue
                case_id = ticket.get("case_id")
                item = by_id.get(case_id)
                if not item or not isinstance(ticket.get("order"), dict):
                    continue
                action = item.get("action")
                if action not in REFUND_ACTIONS:
                    if action == "补充材料" and expected_refund(ticket["order"], fields) is not None:
                        warnings.append("%s 金额数据看似齐全，请确认补充的是证据而非金额" % case_id)
                    continue
                expected = expected_refund(ticket["order"], fields)
                if expected is None:
                    if action in REFUND_ACTIONS:
                        errors.append("%s 金额数据不全却给出退款动作，应改为补充材料" % case_id)
                elif item.get("refund_cents") != expected:
                    errors.append("%s 退款金额应为 %d，实际 %s" %
                                  (case_id, expected, item.get("refund_cents")))

    summary = {
        "total": len(results),
        "by_action": counts,
        "pending_case_ids": pending_ids,
        "pending_count": len(pending_ids),
        "refund_action_count": sum(counts.get(a, 0) for a in REFUND_ACTIONS),
        "refund_total_cents": refund_total,
        "errors": len(errors),
        "warnings": len(warnings),
    }

    print("TOTAL %d" % summary["total"])
    print("BY_ACTION " + " ".join("%s=%d" % (key, counts[key]) for key in sorted(counts)))
    print("PENDING %d %s" % (summary["pending_count"], ",".join(str(x) for x in pending_ids)))
    print("REFUND_TOTAL_CENTS %d" % refund_total)
    for message in warnings:
        print("WARN %s" % message)
    for message in errors:
        print("ERROR %s" % message)

    if args.summary_out:
        with open(args.summary_out, "w", encoding="utf-8") as handle:
            json.dump(summary, handle, ensure_ascii=False, indent=2)
            handle.write("\n")

    if errors:
        print("FAIL %d error(s), %d warning(s)" % (len(errors), len(warnings)))
        return 1
    print("PASS 0 error(s), %d warning(s)" % len(warnings))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)

import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const readJson = (path) => JSON.parse(readFileSync(path, 'utf8'));
const expected = readJson(new URL('./expected.json', import.meta.url));
const coreFields = ['action', 'refund_cents', 'freight'];
const actions = new Set(['退货退款', '直接退款', '补发配件', '补充材料', '物流核查', '人工复核']);
const freightValues = new Set(['商家', '买家', '待定', '不适用']);

function score(gold, actual) {
  assert.ok(Array.isArray(actual), '输出必须是 JSON 数组');
  const byId = new Map();
  for (const row of actual) {
    assert.ok(row && typeof row === 'object', '每条输出必须是对象');
    assert.equal(typeof row.case_id, 'string', '缺少 case_id');
    assert.ok(!byId.has(row.case_id), `重复工单：${row.case_id}`);
    assert.ok(actions.has(row.action), `${row.case_id}: action 不在约定范围`);
    assert.ok(row.refund_cents === null || (Number.isSafeInteger(row.refund_cents) && row.refund_cents >= 0), `${row.case_id}: refund_cents 必须是非负整数或 null`);
    assert.ok(freightValues.has(row.freight), `${row.case_id}: freight 不在约定范围`);
    assert.ok(Array.isArray(row.rules) && row.rules.every((rule) => /^P0[1-7]$/.test(rule)), `${row.case_id}: rules 必须是有效政策编号数组`);
    assert.ok(Array.isArray(row.missing) && row.missing.every((item) => typeof item === 'string'), `${row.case_id}: missing 必须是文本数组`);
    assert.ok(typeof row.reason === 'string' && row.reason.trim(), `${row.case_id}: 缺少 reason`);
    assert.ok(typeof row.customer_reply === 'string' && row.customer_reply.trim(), `${row.case_id}: 缺少 customer_reply`);
    byId.set(row.case_id, row);
  }
  assert.deepEqual([...byId.keys()].sort(), gold.map((row) => row.case_id).sort(), '工单编号集合不一致：存在遗漏或多余工单');
  const cases = gold.map((item) => {
    const row = byId.get(item.case_id);
    const mismatches = coreFields.filter((field) => row[field] !== item[field]).map((field) => ({ field, expected: item[field], actual: row[field] }));
    return {
      case_id: item.case_id,
      core_match: mismatches.length === 0,
      mismatches,
      missing_required_rules: item.rules.filter((rule) => !row.rules.includes(rule)),
      manual_review_note: item.review_note,
    };
  });
  return {
    total: gold.length,
    core_matches: cases.filter((item) => item.core_match).length,
    field_matches: Object.fromEntries(coreFields.map((field) => [field, gold.filter((item) => item[field] === byId.get(item.case_id)[field]).length])),
    required_rule_coverage: cases.filter((item) => item.missing_required_rules.length === 0).length,
    manual_review_required: '逐条核实来源引用、规则适用、补问内容和客户回复；规则覆盖不等于解释正确。',
    cases,
  };
}

function selfTest() {
  for (const [split, gold] of Object.entries(expected)) {
    const inputs = readJson(new URL(`../inputs/${split}.json`, import.meta.url));
    assert.equal(inputs.length, 12);
    assert.equal(new Set(inputs.map((row) => row.case_id)).size, 12);
    assert.deepEqual(inputs.map((row) => row.case_id), gold.map((row) => row.case_id));
    assert.ok(!/"(?:expected_status|review_note|refund_cents|action|rules)"/.test(JSON.stringify(inputs)), '输入混入标准答案字段');
    for (const answer of gold) {
      const input = inputs.find((row) => row.case_id === answer.case_id);
      if (['退货退款', '直接退款'].includes(answer.action)) {
        const order = input.order;
        const amounts = [order.line_original_cents, order.line_coupon_cents, order.line_refunded_cents];
        assert.ok(amounts.every(Number.isSafeInteger));
        assert.equal(answer.refund_cents, amounts[0] - amounts[1] - amounts[2], `${answer.case_id}: 标准金额不一致`);
      }
    }
    const simulated = gold.map(({ review_note, ...row }) => ({ ...row, missing: [], reason: '评分器自检用文本，并非模型输出', customer_reply: '评分器自检用文本' }));
    assert.equal(score(gold, simulated).core_matches, 12);
    const wrongAmount = structuredClone(simulated);
    wrongAmount[0].refund_cents += 1;
    assert.equal(score(gold, wrongAmount).core_matches, 11, '一分钱差异必须被发现');
    const wrongRoute = structuredClone(simulated);
    wrongRoute[0].action = '人工复核';
    assert.equal(score(gold, wrongRoute).field_matches.action, 11);
    const noRule = structuredClone(simulated);
    noRule[0].rules = [];
    assert.equal(score(gold, noRule).required_rule_coverage, 11);
    assert.throws(() => score(gold, simulated.slice(1)), /工单编号集合不一致/);
    assert.throws(() => score(gold, [...simulated, simulated[0]]), /重复工单/);
    const decimal = structuredClone(simulated);
    decimal[0].refund_cents = 1.5;
    assert.throws(() => score(gold, decimal), /非负整数/);
  }
  const transfers = readJson(new URL('../inputs/transfer.json', import.meta.url));
  const hours = (id) => {
    const order = transfers.find((item) => item.case_id === id).order;
    return (Date.parse(order.applied_at) - Date.parse(order.signed_at)) / 3600000;
  };
  assert.equal(hours('T01'), 168);
  assert.ok(hours('T02') > 168);
  assert.equal(hours('T11'), 744);
  console.log('材料与评分器自检通过：24条合成工单；金额、时间边界、漏单、重复、差异识别已检查。这不是 SoduWork 实测成绩。');
}

try {
  const [split, resultPath] = process.argv.slice(2);
  if (split === '--self-test') {
    selfTest();
  } else {
    assert.ok(Object.hasOwn(expected, split ?? '') && resultPath, '用法：node evaluation/score.mjs <development|transfer> <results.json>，或 --self-test');
    console.log(JSON.stringify(score(expected[split], readJson(resultPath)), null, 2));
  }
} catch (error) {
  console.error(error.message);
  process.exitCode = 1;
}

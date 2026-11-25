import { test } from "node:test";
import assert from "node:assert/strict";
import { stuckFor } from "../src/stuck.ts";

const H = 3600e3, now = Date.parse("2026-11-24T20:00:00Z");
const at = (h: number) => new Date(now - h * H).toISOString();
const steps = (o: Record<string, [string, number | null]>) => ["posted", "built", "recorded", "text", "vsl"].map(k =>
  ({ key: k, label: k, at: o[k]?.[1] != null ? at(o[k][1]!) : null, state: o[k]?.[0] ?? "pending" }));

test("built 20 h ago and not recorded is stuck past the 12 h budget", () => {
  const s = stuckFor(steps({ posted: ["done", 30], built: ["done", 20] }), now);
  assert.equal(s?.stage, "built"); assert.equal(s?.waiting_for, "recorded"); assert.equal(s?.hours, 20); assert.equal(s?.budget_h, 12);
});
test("inside the budget is not stuck", () => assert.equal(stuckFor(steps({ posted: ["done", 3] }), now), null));
test("a sent VSL is never stuck", () => assert.equal(stuckFor(steps({ posted: ["done", 99], vsl: ["done", 1] }), now), null));
test("no timed step is not stuck", () => assert.equal(stuckFor(steps({}), now), null));

import { test } from "node:test";
import assert from "node:assert/strict";
import { mkdtempSync, writeFileSync } from "node:fs";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { letterFor, sendFileUrl } from "../src/feed.ts";

const dir = mkdtempSync(join(tmpdir(), "ee-"));
test("letterFor reads the sent cover letter from the drafts folder", () => {
  writeFileSync(join(dir, "6728.txt"), "Hi, I built this.\n");
  const l = letterFor({ letter_file: join(dir, "6728.txt"), proposal_id: "21" }, "2026-11-24T21:53:10Z", dir + "/");
  assert.equal(l?.text, "Hi, I built this."); assert.equal(l?.file, "6728.txt"); assert.equal(l?.proposal_id, "21");
});
test("letterFor refuses a path outside the drafts folder and a missing file", () => {
  assert.equal(letterFor({ letter_file: "/etc/passwd" }, null, dir + "/"), null);
  assert.equal(letterFor({ letter_file: dir + "/../x.txt" }, null, dir + "/"), null);
  assert.equal(letterFor({ letter_file: join(dir, "nope.txt") }, null, dir + "/"), null);
  assert.equal(letterFor({}, null, dir + "/"), null);
});
test("sendFileUrl serves a VSL by its basename when the sender's file exists, else null", () => {
  writeFileSync(join(dir, "8891-take1-final.mp4"), "x");
  assert.equal(sendFileUrl("8891-take1-final.mp4", dir), "/api/vsl/8891-take1-final.mp4");
  assert.equal(sendFileUrl("/tmp/upwork-send/8891-take1-final.mp4", dir), "/api/vsl/8891-take1-final.mp4");
  assert.equal(sendFileUrl("gone.mp4", dir), null);
  assert.equal(sendFileUrl("a.txt", dir), null);
  assert.equal(sendFileUrl(null, dir), null);
});

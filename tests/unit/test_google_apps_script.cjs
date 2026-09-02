"use strict";

const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");

const scriptPath = path.resolve(__dirname, "../../google_apps_script.js");
const source = fs.readFileSync(scriptPath, "utf8")
  .replace("SET_YOUR_RAILWAY_WEBHOOK_EMAIL_URL", "https://bot.example/webhook/email")
  .replace("SET_EMAIL_SECRET_IN_APPS_SCRIPT", "test-email-secret");

const properties = new Map();
const label = {};
const threads = Array.from({length: 31}, (_, index) => {
  const id = `message-${index}`;
  const message = {
    getId: () => id,
    getFrom: () => "notification@cake.vn",
    getSubject: () => index === 0 ? "will retry" : `transaction ${index}`,
    getPlainBody: () => id,
    getDate: () => new Date("2026-09-01T00:00:00Z"),
  };
  return {
    getMessages: () => [message],
    addLabel: () => {},
  };
});

const context = {
  console: {log: () => {}, error: () => {}},
  Date,
  JSON,
  Math,
  LockService: {
    getScriptLock: () => ({tryLock: () => true, releaseLock: () => {}}),
  },
  PropertiesService: {
    getScriptProperties: () => ({
      getProperty: key => properties.get(key) || null,
      setProperty: (key, value) => properties.set(key, String(value)),
      deleteProperty: key => properties.delete(key),
    }),
  },
  GmailApp: {
    search: (_query, offset, count) => threads.slice(offset, offset + count),
    getUserLabelByName: () => label,
    createLabel: () => label,
  },
  UrlFetchApp: {
    fetch: (_url, options) => {
      const payload = JSON.parse(options.payload);
      if (payload.body === "message-0") {
        return {getResponseCode: () => 503, getContentText: () => "retry"};
      }
      return {getResponseCode: () => 200, getContentText: () => '{"ok":true}'};
    },
  },
};

vm.createContext(context);
vm.runInContext(source, context, {filename: scriptPath});

context.checkBankEmails();
assert.equal(properties.get("bank_email_scan_offset"), "30");
const failedAfterFirstPage = JSON.parse(properties.get("failed_msg_retries"));
assert.equal(failedAfterFirstPage["message-0"].attempts, 1);

context.checkBankEmails();
assert.equal(properties.get("bank_email_scan_offset"), "0");
const processed = JSON.parse(properties.get("processed_msg_ids"));
assert.ok(processed["message-30"]);
assert.equal(JSON.parse(properties.get("failed_msg_retries"))["message-0"].attempts, 1);

console.log("google_apps_script pagination retry test passed");

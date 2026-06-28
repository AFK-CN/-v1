#!/usr/bin/env node

const { chromium } = require("playwright");

const pageUrl = process.argv[2];
const timeoutMs = Number(process.env.XHS_BROWSER_TIMEOUT_MS || "20000");
const cdpEndpoint = process.env.XHS_CDP_ENDPOINT || "http://127.0.0.1:9222";

function isVideoUrl(url) {
  return /sns-video|xhscdn.*(?:mp4|video)|\.mp4(?:[?#]|$)/i.test(url);
}

async function main() {
  if (!pageUrl) {
    throw new Error("missing_page_url");
  }
  const browser = await chromium.connectOverCDP(cdpEndpoint);
  const context = browser.contexts()[0] || await browser.newContext();
  const page = await context.newPage();
  const videoUrls = [];
  const remember = (url) => {
    if (isVideoUrl(url) && !videoUrls.includes(url)) {
      videoUrls.push(url);
    }
  };
  page.on("request", (request) => remember(request.url()));
  page.on("response", (response) => remember(response.url()));
  await page.goto(pageUrl, { waitUntil: "domcontentloaded", timeout: timeoutMs });
  await page.waitForTimeout(Math.min(timeoutMs, 15000));
  await page.close().catch(() => {});
  await browser.close().catch(() => {});
  process.stdout.write(JSON.stringify({ video_urls: videoUrls }, null, 2));
}

main().catch((error) => {
  process.stdout.write(JSON.stringify({ video_urls: [], error: String(error && error.message ? error.message : error) }, null, 2));
  process.exitCode = 1;
});

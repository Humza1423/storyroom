import { chromium } from "@playwright/test";
import { mkdir } from "node:fs/promises";
await mkdir("docs/capture-tmp", { recursive: true });
const browser = await chromium.launch();
const context = await browser.newContext({
  viewport: { width: 1512, height: 1050 },
  recordVideo: { dir: "docs/capture-tmp", size: { width: 1512, height: 1050 } },
});
const page = await context.newPage();
await page.goto("http://127.0.0.1:5173");
await page
  .getByRole("button", { name: "First assembly · technical demo" })
  .click();
await page.locator(".clip-row").first().waitFor();
await page.locator(".clip-main").first().click();
await page.waitForFunction(
  () => document.querySelector("video")?.readyState >= 2,
);
await page.waitForTimeout(300);
await page.screenshot({ path: "docs/workspace.png", fullPage: true });
await page.getByRole("button", { name: "Play assembly" }).click();
await page.waitForTimeout(9500);
await page.getByRole("button", { name: "Processing", exact: false }).click();
await page.waitForTimeout(1000);
const video = page.video();
await context.close();
await video.saveAs("docs/demo.webm");
await browser.close();
console.log(
  "Saved docs/workspace.png and docs/demo.webm (generated technical fixture footage).",
);

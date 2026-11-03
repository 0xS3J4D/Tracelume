import { expect, test } from "@playwright/test";

test("case → evidence → ALEAPP job → artifacts → audit", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("img", { name: "Tracelume" })).toBeVisible();

  const name = `Smoke ${Date.now()}`;
  await page.getByLabel("Case name").fill(name);
  await page.getByRole("button", { name: "Create case" }).click();
  await page.getByRole("link", { name }).click();

  await page.getByRole("navigation", { name: "Case sections" }).getByRole("link", { name: "Evidence" }).click();
  await page.getByLabel("Evidence file").setInputFiles({
    name: "synthetic-android.zip", mimeType: "application/zip",
    buffer: Buffer.from("synthetic test data, not real evidence"),
  });
  await page.getByLabel("Type").selectOption("android_fs");
  await page.getByRole("button", { name: "Register evidence" }).click();
  await expect(page.getByText(/Registered synthetic-android.zip/)).toBeVisible();
  await expect(page.getByText(/SHA-256 [0-9a-f]{64}/).first()).toBeVisible();

  await page.getByRole("button", { name: "Run ALEAPP" }).click();
  await expect(page.getByText("succeeded")).toBeVisible();
  await expect(page.getByLabel("Job log")).toContainText("evidence hash verified");

  await page.getByRole("link", { name: "View artifacts →" }).click();
  await expect(page.getByText("6 artifacts")).toBeVisible();
  await page.getByLabel("Search artifacts").fill("synthetic fixture");
  await page.keyboard.press("Enter");
  await expect(page.getByText("1 artifacts")).toBeVisible();
  await expect(page.getByLabel("Artifact details")).toContainText("mmssms.db");

  await page.getByRole("navigation", { name: "Case sections" }).getByRole("link", { name: "Audit log" }).click();
  await expect(page.getByText("hash chain intact")).toBeVisible();
});

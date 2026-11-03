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
  await page.getByLabel("Type", { exact: true }).selectOption("android_fs");
  await page.getByRole("button", { name: "Register evidence" }).click();
  await expect(page.getByText(/Registered synthetic-android.zip/)).toBeVisible();
  await expect(page.getByText(/SHA-256 [0-9a-f]{64}/).first()).toBeVisible();

  await page.getByRole("button", { name: "Choose…" }).click();
  await page.getByRole("menuitem", { name: /ALEAPP/ }).click();
  await expect(page.getByText("succeeded")).toBeVisible();
  await expect(page.getByLabel("Job log")).toContainText("evidence hash verified");

  await page.getByRole("link", { name: "View artifacts →" }).click();
  await expect(page.getByText("6 artifacts")).toBeVisible();
  await page.getByLabel("Search artifacts").fill("synthetic fixture");
  await page.keyboard.press("Enter");
  await expect(page.getByText("1 artifacts")).toBeVisible();
  const details = page.getByLabel("Artifact details");
  await expect(details).toContainText("mmssms.db");

  // tag + note via keyboard
  await page.getByLabel("Artifact table").focus();
  await page.keyboard.press("t");
  await page.keyboard.type("Key evidence");
  await page.keyboard.press("Enter");
  await expect(details.getByRole("button", { name: "Key evidence" })).toHaveAttribute("aria-pressed", "true");
  await page.getByLabel("New note").fill("Consistent with witness statement");
  await page.getByRole("button", { name: /Save note/ }).click();
  await expect(details).toContainText("Consistent with witness statement");

  // conversation + map views
  await page.getByLabel("Search artifacts").fill("");
  await page.keyboard.press("Enter");
  await page.getByLabel("Type", { exact: true }).selectOption("message");
  await expect(page.getByLabel("Messages")).toContainText("Reply in UTC");
  await page.getByLabel("Type", { exact: true }).selectOption("location");
  await expect(page.getByText(/1 of 1 artifacts have coordinates/)).toBeVisible();

  // timeline
  const sections = page.getByRole("navigation", { name: "Case sections" });
  await sections.getByRole("link", { name: "Timeline" }).click();
  await expect(page.getByLabel("Events")).toContainText("Hello from the synthetic fixture");

  // assistant (scripted local model in the e2e server)
  await sections.getByRole("link", { name: "Assistant" }).click();
  await expect(page.getByText(/Local model/)).toBeVisible();
  await page.getByRole("button", { name: "Summarise the case" }).click();
  await expect(page.getByText("Messages found")).toBeVisible();
  await page.getByTitle("Open cited artifact").first().click();
  await expect(page.getByLabel("Artifact details")).toContainText("message");
  await page.getByText(/tool steps?/).click();
  await expect(page.getByText("search_artifacts", { exact: false }).first()).toBeVisible();

  // SQL tab empty state
  await sections.getByRole("link", { name: "SQL" }).click();
  await expect(page.getByText(/No databases extracted yet/)).toBeVisible();

  // command palette global search
  await page.keyboard.press("Control+k");
  await page.getByLabel("Search cases, views and artifacts").fill("Offset honoured");
  await expect(page.getByRole("option", { name: /Offset honoured/ })).toBeVisible();
  await page.keyboard.press("Escape");

  // settings
  await page.getByRole("link", { name: "Settings" }).click();
  await page.getByLabel(/Name recorded/).fill("E2E Examiner");
  await page.getByRole("button", { name: "Save" }).first().click();
  await expect(page.getByRole("status")).toContainText("Examiner saved");
  await page.getByRole("button", { name: "Create backup now" }).click();
  await expect(page.getByText(/tracelume-backup-.*\.tar\.gz/)).toBeVisible();
  await page.getByRole("button", { name: "Test connection" }).click();
  await expect(page.getByText(/Connected/)).toBeVisible();
  await page.goBack();
  await page.goBack();

  // report
  const download = page.waitForEvent("download");
  await page.getByRole("link", { name: "Export PDF report" }).click();
  expect((await download).suggestedFilename()).toMatch(/\.pdf$/);

  await page.getByRole("navigation", { name: "Case sections" }).getByRole("link", { name: "Audit log" }).click();
  await expect(page.getByText("hash chain intact")).toBeVisible();
});

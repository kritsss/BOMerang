import { expect, test } from "@playwright/test";
import { files } from "./fixtures";

const shot = (page: any, name: string) => (process.env.E2E_SHOTS ? page.screenshot({ path: `${process.env.E2E_SHOTS}/${name}.png`, fullPage: true }) : Promise.resolve());

test("upload → link → review → money flow → simulator → export", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByText(/No projects yet|Start a new project/)).toBeVisible();
  await page.getByLabel("Project name").fill(`Smoke ${Date.now()}`);
  await page.getByRole("button", { name: "Create project" }).click();
  await page.locator('input[type="file"]').setInputFiles(Object.entries(files).map(([name, text]) => ({ name, mimeType: "text/csv", buffer: Buffer.from(text) })));
  // map every file: suggestions are pre-filled, the user confirms
  for (let i = 0; i < 4; i++) {
    const save = page.getByRole("button", { name: "Save mapping" });
    await expect(save).toBeVisible();
    const panel = save.locator("xpath=ancestor::div[contains(@class,'border-t')][1]");
    const ftype = await panel.locator("select").first().inputValue();
    if (ftype === "master") {
      await panel.getByRole("checkbox", { name: "hardness" }).check().catch(() => {});
    }
    await save.click();
    await expect(page.getByText(/mapped/).nth(i)).toBeVisible();
  }
  await shot(page, "1-mapped");
  await page.getByRole("button", { name: "Link my data" }).click();
  await expect(page.getByRole("heading", { level: 1 })).toContainText("linked automatically", { timeout: 60_000 });
  await page.getByRole("button", { name: "Skip animation" }).click().catch(() => {});
  await page.waitForTimeout(600);
  await shot(page, "2-linked");
  await page.getByRole("link", { name: /Review \d+ link/ }).click();
  await expect(page.getByRole("button", { name: /Approve link/ })).toBeVisible();
  const factor = page.getByLabel(/how many/);
  if (await factor.count()) await factor.fill("100");
  await shot(page, "3-review");
  await page.getByRole("button", { name: /Approve link/ }).click();
  await expect(page.getByText(/Linked\. Saved as a rule/)).toBeVisible();
  await page.getByRole("link", { name: "3 Money flow" }).click();
  await expect(page.getByText("Difference to the spend cube")).toBeVisible();
  await expect(page.locator("text=/0\\.00/").first()).toBeVisible();
  await shot(page, "4-money");
  await page.getByRole("button", { name: /^\$|^US\$|USD/ }).first().click();
  await expect(page.getByText("How it is counted")).toBeVisible();
  await page.keyboard.press("Escape");
  await page.getByRole("link", { name: "4 Parts" }).click();
  await page.getByRole("button", { name: /PRT-SH1/ }).first().click();
  await expect(page.getByText("Who supplies it → who uses it")).toBeVisible();
  await shot(page, "5-part");
  await page.getByRole("link", { name: /Simulate a price change/ }).click();
  await expect(page.getByText("Every product that uses it")).toBeVisible();
  await shot(page, "6-sim");
  const dl = page.waitForEvent("download");
  await page.getByRole("button", { name: "Export scenario to Excel" }).click();
  const d = await dl;
  expect(d.suggestedFilename()).toMatch(/\.xlsx$/);
});

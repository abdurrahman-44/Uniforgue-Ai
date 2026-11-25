import { expect, test } from "@playwright/test";

test.describe("UNIFORGE AI End-to-End Academic Journey", () => {
  test("register, create project, draft document, export & inspect studios", async ({ page }) => {
    const email = `e2e_${Date.now()}@university.edu`;

    await page.goto("http://localhost:3000/");
    await expect(page.getByText("From Academic Ideas to")).toBeVisible();

    await page.goto("http://localhost:3000/register");
    await page.getByPlaceholder("Amina Al-Mansoor").fill("E2E Scholar");
    await page.getByPlaceholder("amina@university.edu").fill(email);
    await page.getByPlaceholder("••••••••••••").fill("StrongPass123!");
    await page.getByRole("button", { name: "Create Free Account" }).click();

    await expect(page).toHaveURL(/\/dashboard/, { timeout: 15000 });
    await expect(page.getByText("Welcome back, E2E Scholar")).toBeVisible();

    await page.goto("http://localhost:3000/documents");
    await expect(page.getByText("Academic Document Studio")).toBeVisible();

    await page.goto("http://localhost:3000/diagrams");
    await expect(page.getByText("Interactive Diagram Studio")).toBeVisible();

    await page.goto("http://localhost:3000/research");
    await expect(page.getByText("Research & Citation Studio")).toBeVisible();

    await page.goto("http://localhost:3000/videos");
    await expect(page.getByText("AI Video & Storyboard Studio")).toBeVisible();
  });
});

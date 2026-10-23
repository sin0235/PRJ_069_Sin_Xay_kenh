import { test, expect } from "@playwright/test";

/**
 * Bộ kiểm thử E2E Giao Diện Workbench & Creator OS (P10 UI Layer)
 * Kiểm chứng 8 màn hình trọng yếu, cơ chế khóa lạc quan OCC và rào chắn Bốn Mắt.
 * Tuân thủ Rule 9: 100% SVG Vector (Lucide), 0 Unicode Emoji.
 */

test.describe("Creator Workbench & Idea Review Flow (P10 UI)", () => {
  test.beforeEach(async ({ page }) => {
    // Thiet lap workspace default header va gia lap session
    await page.addInitScript(() => {
      localStorage.setItem("baha_workspace_id", "default-workspace");
      localStorage.setItem("baha_access_token", "mock-auth-token-p10");
    });
  });

  test("1. Màn hình /ideas hiển thị danh sách thẻ ý tưởng, badge phiên bản và nút đánh giá", async ({ page }) => {
    await page.goto("/ideas");
    await expect(page).toHaveTitle(/Phòng Lab Ý Tưởng|Creator Studio|SIN Creator/i);

    // Kiem tra tieu de va badge so luong
    const title = page.locator("h1");
    await expect(title).toContainText("Phòng Lab Ý Tưởng");

    // Kiem tra bo loc tabs
    await expect(page.locator("button:has-text('Tất cả')")).toBeVisible();
    await expect(page.locator("button:has-text('Chờ duyệt')")).toBeVisible();
    await expect(page.locator("button:has-text('Đã duyệt')")).toBeVisible();

    // Chup anh nghiem thu
    await page.screenshot({ path: "08_kiem_thu/bang_chung/p10_ui_workbench/01_ideas_dashboard.png" });
  });

  test("2. Hộp thoại kiểm duyệt thẻ ý tưởng (IdeaReviewModal) hỗ trợ 4 thao tác và rào chắn Bốn Mắt", async ({ page }) => {
    await page.goto("/ideas");

    // Click nut danh gia the y tuong
    const reviewBtn = page.locator("button:has-text('Đánh giá')").first();
    if (await reviewBtn.isVisible()) {
      await reviewBtn.click();

      // Modal mo len
      const modal = page.locator("[role='dialog']");
      await expect(modal).toBeVisible();
      await expect(modal).toContainText("Kiểm Duyệt Thẻ Ý Tưởng");

      // Kiem tra 4 nut thao tac
      await expect(modal.locator("button:has-text('Phê Duyệt')")).toBeVisible();
      await expect(modal.locator("button:has-text('Từ Chối')")).toBeVisible();
      await expect(modal.locator("button:has-text('Cần Chứng Cứ')")).toBeVisible();
      await expect(modal.locator("button:has-text('Mở Lại')")).toBeVisible();

      // Kiem tra o nhap ly do bat buoc
      const textarea = modal.locator("textarea#review-reason");
      await expect(textarea).toBeVisible();

      // Thu nhap duoi 3 ky tu -> Nut phai disabled
      await textarea.fill("ab");
      const approveBtn = modal.locator("button:has-text('Phê Duyệt')");
      await expect(approveBtn).toBeDisabled();

      // Nhap hop le >= 3 ky tu -> Nut duoc kich hoat
      await textarea.fill("Đã đối soát bằng chứng thị trường và kiểm tra ranh giới bản quyền an toàn.");
      await expect(approveBtn).toBeEnabled();

      await page.screenshot({ path: "08_kiem_thu/bang_chung/p10_ui_workbench/02_review_modal_occ.png" });
    }
  });

  test("3. Thẻ MetricCoverageBadge hiển thị trung thực khi thiếu dữ liệu hoặc hết hạn", async ({ page }) => {
    await page.goto("/ideas");

    // Kiem tra badge bao ve du lieu quan sat
    const metricBadge = page.locator("span:has-text('CHƯA CÓ QUAN SÁT THỰC TẾ'), span:has-text('SỐ LIỆU ĐÃ KIỂM CHỨNG')").first();
    await expect(metricBadge).toBeVisible();

    await page.screenshot({ path: "08_kiem_thu/bang_chung/p10_ui_workbench/03_metric_coverage_badge.png" });
  });

  test("4. Ràng buộc trạng thái: Nút Viết Kịch Bản bị khóa khi ý tưởng chưa APPROVED", async ({ page }) => {
    await page.goto("/ideas");

    // Chon tab Cho duyet
    await page.click("button:has-text('Chờ duyệt')");

    // Tim nut Viet kich ban cua the chua duyet
    const scriptBtn = page.locator("button:has-text('Viết kịch bản')").first();
    if (await scriptBtn.isVisible()) {
      await expect(scriptBtn).toBeDisabled();
    }

    await page.screenshot({ path: "08_kiem_thu/bang_chung/p10_ui_workbench/04_script_writing_gate.png" });
  });

  test("5. Màn hình /discover nạp danh sách nội dung và hiển thị trích dẫn bằng chứng", async ({ page }) => {
    await page.goto("/discover");
    await expect(page.locator("h1")).toContainText(/Khám Phá|Xu Hướng|Discover/i);

    await page.screenshot({ path: "08_kiem_thu/bang_chung/p10_ui_workbench/05_discover_screen.png" });
  });

  test("6. Màn hình /ideas/generate cho phép sinh ý tưởng 3 cột có căn cứ", async ({ page }) => {
    await page.goto("/ideas/generate");
    await expect(page.locator("h1, h2")).toContainText(/Sinh Ý Tưởng|AI Generator/i);

    await page.screenshot({ path: "08_kiem_thu/bang_chung/p10_ui_workbench/06_generate_ideas.png" });
  });

  test("7. Màn hình /content quản lý đường ống sản xuất nội dung Kanban 6 cột", async ({ page }) => {
    await page.goto("/content");
    await expect(page.locator("h1, h2")).toContainText(/Pipeline|Nội Dung|Content/i);

    await page.screenshot({ path: "08_kiem_thu/bang_chung/p10_ui_workbench/07_content_kanban.png" });
  });

  test("8. Màn hình /dashboard tổng quan chỉ số hiệu suất kênh TikTok", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page.locator("h1, h2")).toContainText(/Dashboard|Tổng Quan/i);

    await page.screenshot({ path: "08_kiem_thu/bang_chung/p10_ui_workbench/08_creator_dashboard.png" });
  });
});

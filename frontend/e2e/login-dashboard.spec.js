import { expect, test } from '@playwright/test'

test('login flow navigates to overview page', async ({ page }) => {
  await page.route('**/api/v1/auth/login', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        access_token: 'test-token',
        token_type: 'bearer',
        expires_in: 3600,
      }),
    })
  })

  await page.route('**/api/v1/analyses**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        items: [],
        total: 0,
        page: 1,
        page_size: 10,
        sort_by: 'created_at',
        sort_order: 'desc',
        limit: 10,
        offset: 0,
      }),
    })
  })

  await page.goto('/login')
  await page.getByPlaceholder('admin').fill('admin')
  await page.getByPlaceholder('请输入密码').fill('admin123')
  await page.getByRole('button', { name: '登录系统' }).click()

  await expect(page).toHaveURL(/app\/overview/)
  await expect(page.getByRole('heading', { name: '导航总览' })).toBeVisible()
})

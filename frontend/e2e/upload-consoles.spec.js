import { expect, test } from '@playwright/test'

const emlPath = '/tmp/pea-upload-smoke.eml'
const sandboxSamplePath = '/Users/qwx/dev/code/PEA_Agent/Eml_Agent/rules/yara/00_generic.yar'

async function login(page) {
  await page.goto('/login')
  await page.getByPlaceholder('admin').fill('admin')
  await page.getByPlaceholder('请输入密码').fill('123456')
  await page.getByRole('button', { name: '登录系统' }).click()
  await expect(page).toHaveURL(/app\/overview/)
}

test.describe('upload consoles', () => {
  test.setTimeout(120_000)

  test('email upload console validates and submits a real eml file', async ({ page }) => {
    await login(page)

    await page.goto('/app/upload')
    await expect(page.getByRole('heading', { name: '上传分析' })).toBeVisible()
    await expect(page.getByRole('heading', { name: '邮件上传台' })).toBeVisible()

    await page.getByRole('button', { name: '开始分析' }).click()
    await expect(page.getByText('请先选择 .eml 文件')).toBeVisible()

    await page.locator('input[type="file"]').setInputFiles(emlPath)
    await expect(page.getByText('pea-upload-smoke.eml')).toBeVisible()

    await page.getByRole('button', { name: '开始分析' }).click()
    await expect(page.getByRole('button', { name: '查看分析结果' })).toBeVisible({ timeout: 90_000 })
    await expect(page.getByText(/分析完成|命中历史缓存/)).toBeVisible({ timeout: 5_000 })
  })

  test('static sandbox console validates and scans a real local file', async ({ page }) => {
    await login(page)

    await page.goto('/app/static-sandbox')
    await expect(page.getByRole('heading', { name: '静态沙箱上传扫描' })).toBeVisible()
    await expect(page.getByRole('heading', { name: '静态样本上传台' })).toBeVisible()

    await page.getByRole('button', { name: '开始扫描' }).click()
    await expect(page.getByText('请先选择附件样本')).toBeVisible()

    await page.locator('input[type="file"]').setInputFiles(sandboxSamplePath)
    await expect(page.getByText('00_generic.yar')).toBeVisible()

    await page.getByRole('button', { name: '开始扫描' }).click()
    await expect(page.getByRole('heading', { name: '扫描结果' })).toBeVisible({ timeout: 30_000 })
    await expect(page.getByText(/静态沙箱分析完成|任务已完成，但结果为 error/)).toBeVisible({ timeout: 5_000 })
  })
})

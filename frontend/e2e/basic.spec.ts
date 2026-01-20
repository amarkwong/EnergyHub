import { test, expect } from '@playwright/test'

test.describe('EnergyHub Basic Tests', () => {
  test('homepage loads successfully', async ({ page }) => {
    await page.goto('/')

    // Check page title
    await expect(page).toHaveTitle(/EnergyHub/)

    // Check header is visible
    await expect(page.getByText('EnergyHub')).toBeVisible()
  })

  test('navigation works', async ({ page }) => {
    await page.goto('/')

    // Navigate to Upload page
    await page.getByRole('link', { name: 'Upload Data' }).click()
    await expect(page).toHaveURL('/upload')
    await expect(page.getByText('Upload NEM12')).toBeVisible()

    // Navigate to Consumption page
    await page.getByRole('link', { name: 'Consumption' }).click()
    await expect(page).toHaveURL('/consumption')

    // Navigate to Reconciliation page
    await page.getByRole('link', { name: 'Reconciliation' }).click()
    await expect(page).toHaveURL('/reconciliation')

    // Navigate to Tariffs page
    await page.getByRole('link', { name: 'Tariffs' }).click()
    await expect(page).toHaveURL('/tariffs')
  })

  test('dashboard shows quick actions', async ({ page }) => {
    await page.goto('/')

    // Check quick actions are displayed
    await expect(page.getByText('Quick Actions')).toBeVisible()
    await expect(page.getByText('Upload NEM12')).toBeVisible()
    await expect(page.getByText('Upload Invoice')).toBeVisible()
    await expect(page.getByText('Run Reconciliation')).toBeVisible()
  })

  test('tariffs page shows providers', async ({ page }) => {
    await page.goto('/tariffs')

    // Check providers are displayed
    await expect(page.getByText('Network Tariffs')).toBeVisible()
    await expect(page.getByRole('button', { name: 'Ausgrid' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Energex' })).toBeVisible()

    // Filter by state
    await page.getByRole('button', { name: 'VIC' }).click()
    await expect(page.getByRole('button', { name: 'CitiPower' })).toBeVisible()
  })

  test('upload page has file input', async ({ page }) => {
    await page.goto('/upload')

    // Check upload type buttons
    await expect(page.getByRole('button', { name: 'NEM12 File' })).toBeVisible()
    await expect(page.getByRole('button', { name: 'Invoice PDF' })).toBeVisible()

    // Check dropzone is visible
    await expect(page.getByText('Upload NEM12 file')).toBeVisible()
  })

  test('reconciliation page shows sample data', async ({ page }) => {
    await page.goto('/reconciliation')

    // Check reconciliation elements
    await expect(page.getByText('Invoice Reconciliation')).toBeVisible()
    await expect(page.getByText('Line Item Breakdown')).toBeVisible()
    await expect(page.getByText('Recommendations')).toBeVisible()
  })
})

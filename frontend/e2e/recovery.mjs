// Simulates a serverless restart: the API forgets the upload, the app must re-send it silently.
import { chromium } from '@playwright/test'
import { execSync } from 'node:child_process'
const BASE = 'http://localhost:4173', CSV = process.argv[2], RESTART = process.argv[3]
const browser = await chromium.launch({ executablePath: '/usr/bin/google-chrome' })
const page = await (await browser.newContext({ viewport: { width: 1366, height: 900 } })).newPage()
const errors = []; page.on('pageerror', (e) => errors.push(e.message))
await page.goto(BASE + '/app/data', { waitUntil: 'networkidle' })
await page.setInputFiles('input[type=file]', CSV)
await page.getByText('Prepare data →').click()
await page.waitForURL('**/app/quality', { timeout: 120000 })
console.log('✓ upload prepared')
execSync(RESTART, { stdio: 'inherit' })
console.log('✓ API restarted (upload forgotten on the server)')
await page.goto(BASE + '/app/dashboard', { waitUntil: 'networkidle' })
await page.locator('.kpi', { hasText: 'Gross revenue' }).waitFor({ timeout: 120000 })
console.log('✓ dashboard after restart, gross revenue =', await page.locator('.kpi', { hasText: 'Gross revenue' }).locator('.kpi-value').innerText())
console.log('  dataset =', await page.locator('.dataset-chip b').innerText())
console.log('errors:', errors.length ? errors : 'none')
await browser.close()

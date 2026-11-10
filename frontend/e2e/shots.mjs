// Visual check: screenshots of every page at desktop and phone widths, and console errors.
import { chromium } from '@playwright/test'
const BASE = process.env.BASE || 'http://localhost:4173'
const OUT = process.argv[2] || 'shots'
const pages = ['/', '/app', '/app/data', '/app/quality', '/app/eda', '/app/dashboard', '/app/forecast', '/app/insights', '/app/reports']
const sizes = (process.env.SIZES || 'desktop').split(',')
const vp = { desktop: { width: 1440, height: 900 }, tablet: { width: 820, height: 1100 }, phone: { width: 390, height: 844 } }
const browser = await chromium.launch({ executablePath: '/usr/bin/google-chrome', args: ['--use-gl=swiftshader', '--enable-webgl', '--ignore-gpu-blocklist'] })
for (const s of sizes) {
  const ctx = await browser.newContext({ viewport: vp[s], deviceScaleFactor: 1 })
  const page = await ctx.newPage()
  const errors = []
  page.on('console', (m) => { if (m.type() === 'error') errors.push(m.text().slice(0, 200)) })
  page.on('pageerror', (e) => errors.push('PAGEERROR ' + e.message.slice(0, 200)))
  for (const p of (process.env.PAGES ? process.env.PAGES.split(',') : pages)) {
    await page.goto(BASE + p, { waitUntil: 'networkidle', timeout: 120000 })
    await page.waitForTimeout(p === '/app/forecast' || p === '/app/insights' ? 6000 : 2500)
    const w = await page.evaluate(() => document.documentElement.scrollWidth - window.innerWidth)
    const name = `${OUT}/${s}${p.replace(/\//g, '_') || '_home'}.png`
    await page.screenshot({ path: name, fullPage: process.env.FULL === '1' })
    console.log(s, p, 'overflowX=', w)
  }
  console.log(s, 'console errors:', errors.length ? errors : 'none')
  await ctx.close()
}
await browser.close()

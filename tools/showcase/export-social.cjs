// Render code-native layouts of untouched product screenshots for sharing.
// Requires Playwright and Chromium; no network access or image generation.
const { chromium } = require(process.env.PLAYWRIGHT_MODULE || 'playwright')
const path = require('path')
const fs = require('fs')
;(async () => {
  const browser = await chromium.launch({executablePath:process.env.CHROMIUM_PATH || '/usr/bin/chromium',headless:true,args:['--no-sandbox']})
  const output = '/tmp/keystroke-press-kit'
  fs.mkdirSync(output,{recursive:true})
  const modes = [
    ['landscape',null,800,'keystroke-showcase.png'],
    ['square',null,1200,'keystroke-square.png'],
    ['social',null,630,'social-card.png'],
    ...['codex','voice','clipboard','calculator'].map(shot=>['single',shot,900,'keystroke-'+shot+'.png'])
  ]
  for (const [mode,shot,height,name] of modes) {
    const page = await browser.newPage({viewport:{width:1200,height},deviceScaleFactor:2})
    await page.goto('file://'+path.join(__dirname,'social.html')+'?mode='+mode+(shot?'&shot='+shot:''))
    await page.evaluate(async()=>{await document.fonts.ready;await Promise.all(Array.from(document.images).map(i=>i.decode()))})
    await page.screenshot({path:path.join(output,name)})
    console.log(name)
    await page.close()
  }
  await browser.close()
})().catch(error=>{console.error(error);process.exit(1)})

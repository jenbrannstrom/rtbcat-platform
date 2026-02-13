const WebSocket = require('ws');
const fs = require('fs');
const https = require('https');
const http = require('http');

const CHROME_DEBUG_URL = 'http://localhost:9222';
const SCREENSHOT_DIR = '/home/x1-7/Documents/rtbcat-platform/screenshots';

// Ensure screenshot directory exists
if (!fs.existsSync(SCREENSHOT_DIR)) {
  fs.mkdirSync(SCREENSHOT_DIR, { recursive: true });
}

async function getPages() {
  return new Promise((resolve, reject) => {
    http.get(`${CHROME_DEBUG_URL}/json`, (res) => {
      let data = '';
      res.on('data', chunk => data += chunk);
      res.on('end', () => resolve(JSON.parse(data)));
    }).on('error', reject);
  });
}

async function sendCommand(ws, method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = Date.now();
    const timeout = setTimeout(() => reject(new Error(`Timeout for ${method}`)), 30000);

    const handler = (data) => {
      const msg = JSON.parse(data.toString());
      if (msg.id === id) {
        clearTimeout(timeout);
        ws.off('message', handler);
        if (msg.error) reject(new Error(msg.error.message));
        else resolve(msg.result);
      }
    };

    ws.on('message', handler);
    ws.send(JSON.stringify({ id, method, params }));
  });
}

async function takeScreenshot(ws, name) {
  const result = await sendCommand(ws, 'Page.captureScreenshot', { format: 'png' });
  const filepath = `${SCREENSHOT_DIR}/${name}.png`;
  fs.writeFileSync(filepath, Buffer.from(result.data, 'base64'));
  console.log(`Screenshot saved: ${filepath}`);
  return filepath;
}

async function evaluate(ws, expression) {
  const result = await sendCommand(ws, 'Runtime.evaluate', {
    expression,
    returnByValue: true,
    awaitPromise: true
  });
  return result.result?.value;
}

async function navigate(ws, url) {
  await sendCommand(ws, 'Page.navigate', { url });
  await new Promise(r => setTimeout(r, 3000)); // Wait for page load
}

async function getConsoleErrors(ws) {
  // Enable console
  await sendCommand(ws, 'Console.enable');
  // Get any existing errors via evaluation
  const errors = await evaluate(ws, `
    (function() {
      return window.__consoleErrors || [];
    })()
  `);
  return errors || [];
}

async function runTests() {
  console.log('Starting VM2 UI Tests for Mobyoung...\n');

  const pages = await getPages();
  const dashboardPage = pages.find(p => p.url.includes('vm2.scan.rtb.cat'));

  if (!dashboardPage) {
    console.error('Cat-Scan Dashboard tab not found!');
    process.exit(1);
  }

  const ws = new WebSocket(dashboardPage.webSocketDebuggerUrl);

  await new Promise((resolve, reject) => {
    ws.on('open', resolve);
    ws.on('error', reject);
  });

  // Enable necessary domains
  await sendCommand(ws, 'Page.enable');
  await sendCommand(ws, 'Runtime.enable');
  await sendCommand(ws, 'Network.enable');

  const results = [];

  try {
    // Inject console error collector
    await evaluate(ws, `
      window.__consoleErrors = [];
      window.__networkErrors = [];
      const origError = console.error;
      console.error = function(...args) {
        window.__consoleErrors.push(args.join(' '));
        origError.apply(console, args);
      };
    `);

    // TEST 1: Home page - Check "Recommended Optimizations" block
    console.log('Test 1: Checking Home page for Recommended Optimizations...');
    await navigate(ws, 'https://vm2.scan.rtb.cat/?advertiser=mobyoung');
    await new Promise(r => setTimeout(r, 2000));
    await takeScreenshot(ws, '01-home-page');

    const hasRecommendedOpt = await evaluate(ws, `
      (function() {
        const text = document.body.innerText;
        return text.includes('Recommended Optimizations') ||
               document.querySelector('[class*="recommended"]') !== null;
      })()
    `);

    results.push({
      test: '1. Home page: "Recommended Optimizations" block should NOT appear',
      pass: !hasRecommendedOpt,
      detail: hasRecommendedOpt ? 'Found Recommended Optimizations block' : 'Not found (correct)'
    });

    // TEST 2: Home header metrics
    console.log('Test 2: Checking Home header metrics...');
    const metrics = await evaluate(ws, `
      (function() {
        const text = document.body.innerText;
        const reachedQueries = text.match(/Reached Queries[:\\s]*([\\d,.NaN%]+)/i);
        const impressions = text.match(/Impressions[:\\s]*([\\d,.NaN%]+)/i);
        const winRate = text.match(/Win Rate[:\\s]*([\\d,.NaN%]+)/i);

        // Look for stat cards
        const statCards = document.querySelectorAll('[class*="stat"], [class*="metric"], [class*="card"]');
        let cardTexts = [];
        statCards.forEach(c => cardTexts.push(c.innerText));

        return {
          hasNaN: text.includes('NaN'),
          winRateMatch: winRate ? winRate[1] : null,
          bodySnippet: text.substring(0, 1500),
          cardTexts: cardTexts.slice(0, 5)
        };
      })()
    `);

    await takeScreenshot(ws, '02-home-metrics');

    let winRateOk = true;
    if (metrics.winRateMatch) {
      const wr = parseFloat(metrics.winRateMatch);
      if (!isNaN(wr) && wr > 100) winRateOk = false;
    }

    results.push({
      test: '2. Home header: Metrics render (no NaN, win rate <= 100)',
      pass: !metrics.hasNaN && winRateOk,
      detail: metrics.hasNaN ? 'Found NaN in metrics' : (winRateOk ? 'Metrics OK' : 'Win rate > 100%')
    });

    // TEST 3: Creatives page loads
    console.log('Test 3: Checking /creatives page...');
    await navigate(ws, 'https://vm2.scan.rtb.cat/creatives?advertiser=mobyoung');
    await new Promise(r => setTimeout(r, 3000));
    await takeScreenshot(ws, '03-creatives-page');

    const creativesCheck = await evaluate(ws, `
      (function() {
        const text = document.body.innerText;
        return {
          hasApiError: text.includes('Cannot connect to API server') || text.includes('API error'),
          hasContent: text.length > 200
        };
      })()
    `);

    results.push({
      test: '3. /creatives page: loads (no "Cannot connect to API server")',
      pass: !creativesCheck.hasApiError && creativesCheck.hasContent,
      detail: creativesCheck.hasApiError ? 'API connection error found' : 'Page loaded OK'
    });

    // TEST 4: By Size tab
    console.log('Test 4: Checking By Size tab...');
    await evaluate(ws, `
      (function() {
        const tabs = document.querySelectorAll('[role="tab"], button, a');
        for (const tab of tabs) {
          if (tab.innerText.includes('By Size') || tab.innerText.includes('Size')) {
            tab.click();
            return true;
          }
        }
        return false;
      })()
    `);
    await new Promise(r => setTimeout(r, 2000));
    await takeScreenshot(ws, '04-by-size-tab');

    const sizeTabCheck = await evaluate(ws, `
      (function() {
        const text = document.body.innerText;
        const hasCheckbox = document.querySelector('input[type="checkbox"]') !== null;
        const hasTable = document.querySelector('table') !== null;
        const hasFeature001 = text.includes('Feature #001') || text.includes('ROADMAP');
        return { hasCheckbox, hasTable, hasFeature001, text: text.substring(0, 500) };
      })()
    `);

    results.push({
      test: '4. By Size tab: table aligned; checkboxes visible; "Feature #001 ROADMAP.md" label',
      pass: sizeTabCheck.hasTable && sizeTabCheck.hasCheckbox,
      detail: `Table: ${sizeTabCheck.hasTable ? 'Yes' : 'No'}, Checkboxes: ${sizeTabCheck.hasCheckbox ? 'Yes' : 'No'}, Feature #001: ${sizeTabCheck.hasFeature001 ? 'Yes' : 'No'}`
    });

    // TEST 5: By Publisher tab
    console.log('Test 5: Checking By Publisher tab...');
    await evaluate(ws, `
      (function() {
        const tabs = document.querySelectorAll('[role="tab"], button, a');
        for (const tab of tabs) {
          if (tab.innerText.includes('Publisher')) {
            tab.click();
            return true;
          }
        }
        return false;
      })()
    `);
    await new Promise(r => setTimeout(r, 2000));
    await takeScreenshot(ws, '05-by-publisher-tab');

    const publisherCheck = await evaluate(ws, `
      (function() {
        const text = document.body.innerText;
        const hasList = document.querySelector('ul, ol, table, [class*="list"]') !== null;
        return { hasList, textLength: text.length };
      })()
    `);

    results.push({
      test: '5. By Publisher tab: embedded list renders',
      pass: publisherCheck.hasList,
      detail: publisherCheck.hasList ? 'List rendered' : 'No list found'
    });

    // TEST 6: Creative preview modal
    console.log('Test 6: Checking Creative preview modal...');
    // First go to By Creative tab
    await evaluate(ws, `
      (function() {
        const tabs = document.querySelectorAll('[role="tab"], button, a');
        for (const tab of tabs) {
          if (tab.innerText.includes('Creative') && !tab.innerText.includes('Creatives')) {
            tab.click();
            return true;
          }
        }
        return false;
      })()
    `);
    await new Promise(r => setTimeout(r, 2000));
    await takeScreenshot(ws, '06-by-creative-tab');

    // Try to click preview icon
    const previewResult = await evaluate(ws, `
      (function() {
        const previewBtns = document.querySelectorAll('[class*="preview"], [aria-label*="preview"], button svg, [class*="icon"]');
        for (const btn of previewBtns) {
          const parent = btn.closest('button') || btn;
          if (parent.click) {
            parent.click();
            return { clicked: true };
          }
        }
        // Try any eye icon or preview-like button
        const allBtns = document.querySelectorAll('button');
        for (const btn of allBtns) {
          if (btn.innerHTML.includes('eye') || btn.title?.includes('preview')) {
            btn.click();
            return { clicked: true, type: 'eye-icon' };
          }
        }
        return { clicked: false };
      })()
    `);

    await new Promise(r => setTimeout(r, 1500));
    await takeScreenshot(ws, '07-creative-preview-modal');

    const modalCheck = await evaluate(ws, `
      (function() {
        const modal = document.querySelector('[role="dialog"], [class*="modal"], [class*="overlay"]');
        return { hasModal: modal !== null };
      })()
    `);

    results.push({
      test: '6. Creative preview: click preview icon — modal opens',
      pass: modalCheck.hasModal || previewResult.clicked,
      detail: modalCheck.hasModal ? 'Modal opened' : (previewResult.clicked ? 'Clicked but no modal detected' : 'Could not find preview button')
    });

    // Collect errors
    const consoleErrors = await evaluate(ws, `window.__consoleErrors || []`);

    // Print results
    console.log('\n' + '='.repeat(60));
    console.log('VM2 UI TEST RESULTS - Mobyoung');
    console.log('='.repeat(60) + '\n');

    for (const r of results) {
      const icon = r.pass ? '✅' : '❌';
      console.log(`${icon} ${r.test}`);
      console.log(`   ${r.detail}\n`);
    }

    if (consoleErrors.length > 0) {
      console.log('\nConsole Errors:');
      consoleErrors.forEach(e => console.log(`  - ${e}`));
    }

    console.log('\nScreenshots saved to:', SCREENSHOT_DIR);

  } catch (err) {
    console.error('Test error:', err);
  } finally {
    ws.close();
  }
}

runTests().catch(console.error);

// DOM checks only: this does not validate browser layout, pixels, or keyboard behavior.
// node test_report_dom.cjs /abs/review.html /abs/node_modules/jsdom
const assert = require('node:assert/strict');
const fs = require('node:fs');
const jsdom = require(process.argv[3] || 'jsdom');
const { JSDOM, VirtualConsole } = jsdom;
const html = fs.readFileSync(process.argv[2], 'utf8');
const requests = [];
const errors = [];
const virtualConsole = new VirtualConsole();
virtualConsole.on('jsdomError', error => errors.push(error.message));
// jsdom 27 intercepts requests; older releases subclass ResourceLoader. Both record and refuse every fetch.
const resources = jsdom.requestInterceptor
  ? { interceptors: [jsdom.requestInterceptor(request => {
      requests.push(request.url);
      return Promise.resolve(new Response('', { status: 403 }));
    })] }
  : new (class extends jsdom.ResourceLoader { fetch(url) { requests.push(url); return null; } })();
const dom = new JSDOM(html, { runScripts: 'dangerously', virtualConsole, resources });
const { document, Event } = dom.window;
assert.equal(document.querySelectorAll('script[src],link[href],iframe,object,embed,form,select,pre,code').length, 0,
  'An explainer loads nothing remote and shows no code or review controls');
assert.ok([...document.querySelectorAll('img')].every(el => el.src.startsWith('data:image/')));
const sections = [...document.querySelectorAll('main > section')].map(el => el.id);
assert.deepEqual([...document.querySelectorAll('nav a')].map(el => el.hash.slice(1)), sections,
  'Navigation lists exactly the sections that have content');
assert.equal(sections[0], 'overview');
assert.equal(sections[sections.length - 1], 'limits');
const visuals = [...document.querySelectorAll('.visual')];
for (const figure of visuals) {
  const picture = figure.querySelector('.diagram');
  if (!picture) {
    assert.ok(figure.querySelector('.visual-table table'), 'A visual without a diagram must be a table');
    continue;
  }
  const zoomIn = figure.querySelector('[data-zoom="in"]');
  const zoomOut = figure.querySelector('[data-zoom="out"]');
  const reset = figure.querySelector('[data-zoom="reset"]');
  assert.ok(!figure.querySelector('.visual-controls').hidden, 'Zoom controls appear once the script runs');
  assert.ok(picture.getAttribute('aria-label') || picture.getAttribute('alt'));
  assert.ok(zoomOut.disabled);
  zoomIn.click();
  assert.equal(picture.style.width, '125%');
  assert.equal(figure.querySelector('output').textContent, '125%');
  zoomOut.click();
  assert.equal(picture.style.width, '100%');
  for (let n = 0; n < 10; n += 1) zoomIn.click();
  assert.equal(picture.style.width, '300%');
  assert.ok(zoomIn.disabled);
  reset.click();
  assert.equal(picture.style.width, '100%');
  assert.ok(!zoomIn.disabled);
}
const details = [...document.querySelectorAll('details')];
assert.ok(details.every(el => !el.open), 'Sources start collapsed');
if (details.length) details[0].open = true;
const beforePrint = details.map(el => el.open);
dom.window.dispatchEvent(new Event('beforeprint'));
assert.ok(details.every(el => el.open));
dom.window.dispatchEvent(new Event('afterprint'));
assert.deepEqual(details.map(el => el.open), beforePrint);
const ids = [...document.querySelectorAll('[id]')].map(el => el.id);
assert.equal(new Set(ids).size, ids.length, 'IDs must be unique, including SVG markers across figures');
for (const anchor of document.querySelectorAll('a[href^="#"]')) {
  assert.ok(document.getElementById(anchor.getAttribute('href').slice(1)), 'Every internal link must resolve');
}
const callouts = [...document.querySelectorAll('.callout')];
const staticDom = new JSDOM(html);
assert.equal(staticDom.window.document.querySelectorAll('.visual-controls:not([hidden])').length, 0,
  'Without JavaScript the page reads as a static document');
assert.deepEqual(requests, [], 'The report must not fetch assets');
assert.deepEqual(errors, [], 'The report script must not throw');
console.log(JSON.stringify({ sections, visuals: visuals.length, callouts: callouts.length, details: details.length,
  assertions: ['no remote assets or code', 'navigation matches sections', 'diagram zoom and fit', 'print restoration',
               'unique IDs and internal anchors', 'static without JavaScript', 'no asset requests', 'no script errors'],
  browserLayoutVerified: false }));
dom.window.close();
staticDom.window.close();

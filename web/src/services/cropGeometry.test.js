import test from 'node:test';
import assert from 'node:assert/strict';
import { availablePaperSources, paperLocationUrl, parsePaperLocation, resolvePaperLocation, resolvePostRenderCrop } from './cropGeometry.js';

test('uses post-render right and bottom as crop-box endpoints', () => {
  assert.deepEqual(resolvePostRenderCrop(1475, 794, {
    left: 3, top: 0, right: 1473, bottom: 590,
  }), { left: 3, top: 0, right: 1473, bottom: 590 });
});

test('clamps malformed post-render crop coordinates to the rendered clip', () => {
  assert.deepEqual(resolvePostRenderCrop(100, 50, {
    left: -5, top: 60, right: 200, bottom: -1,
  }), { left: 0, top: 49, right: 100, bottom: 50 });
});

test('builds and parses an internal source PDF location', () => {
  const url = paperLocationUrl('https://example.test/paper.pdf', [{
    pageIndex: 7,
    x0: 42.2,
    y0: 98.4,
    x1: 242.2,
    y1: 298.4,
    renderDpi: 144,
    postLeft: 10,
    postTop: 20,
    postRight: 300,
    postBottom: 360,
  }], 'answer');
  assert.deepEqual(parsePaperLocation(url), {
    sourceUrl: 'https://example.test/paper.pdf',
    kind: 'answer',
    pageNumber: 8,
    region: { left: 47.2, top: 108.4, right: 192.2, bottom: 278.4 },
  });
});

test('uses the final post-render crop for the highlighted PDF area', () => {
  assert.deepEqual(resolvePaperLocation({
    pageIndex: 2,
    x0: 10,
    y0: 20,
    x1: 110,
    y1: 220,
    renderDpi: 144,
    postLeft: 4,
    postTop: 8,
    postRight: 180,
    postBottom: 360,
  }), { pageNumber: 3, left: 12, top: 24, right: 100, bottom: 200 });
});

test('keeps a question paper available when STEP has no pairable answer', () => {
  const sources = availablePaperSources({
    paperUrl: 'https://example.test/step-paper.pdf',
    answerUrl: '',
    crops: [{ sourceType: 0, pageIndex: 2 }, { sourceType: 1, pageIndex: 4 }],
  });
  assert.deepEqual(sources, [{
    key: 'question',
    url: 'https://example.test/step-paper.pdf',
    regions: [{ sourceType: 0, pageIndex: 2 }],
  }]);
});

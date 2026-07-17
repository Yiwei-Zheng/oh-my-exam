import assert from 'node:assert/strict';
import test from 'node:test';
import { isMobileImageUploadDevice } from './device.js';

const mediaMatcher = (...matchedQueries) => (query) => ({ matches: matchedQueries.includes(query) });

test('uses the browser mobile hint when available', () => {
  assert.equal(isMobileImageUploadDevice({
    navigatorObject: { userAgentData: { mobile: true } },
    matchMedia: mediaMatcher(),
  }), true);
});

test('treats narrow responsive layouts as mobile upload layouts', () => {
  assert.equal(isMobileImageUploadDevice({
    navigatorObject: {},
    matchMedia: mediaMatcher('(max-width: 680px)'),
  }), true);
});

test('supports coarse-pointer phones in landscape orientation', () => {
  assert.equal(isMobileImageUploadDevice({
    navigatorObject: {},
    matchMedia: mediaMatcher('(pointer: coarse)', '(max-width: 1024px)'),
  }), true);
});

test('keeps a desktop viewport on the direct file picker flow', () => {
  assert.equal(isMobileImageUploadDevice({
    navigatorObject: { userAgentData: { mobile: false } },
    matchMedia: mediaMatcher(),
  }), false);
});

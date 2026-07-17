import assert from 'node:assert/strict';
import test from 'node:test';
import { normalizeProxyUrl, readWindowsClientProxy, resolveClientProxyUrl } from './clientProxy.js';

test('normalizes plain and protocol-specific client proxy settings', () => {
  assert.equal(normalizeProxyUrl('127.0.0.1:7890'), 'http://127.0.0.1:7890/');
  assert.equal(normalizeProxyUrl('http=127.0.0.1:8080;https=127.0.0.1:8443'), 'http://127.0.0.1:8443/');
  assert.equal(normalizeProxyUrl('socks=127.0.0.1:1080'), null);
});

test('prefers explicit environment configuration', () => {
  const execute = () => { throw new Error('registry should not be queried'); };
  assert.equal(
    resolveClientProxyUrl({ env: { OH_MY_EXAM_PROXY: 'http://localhost:9000' }, platform: 'win32', execute }),
    'http://localhost:9000/',
  );
});

test('reads an enabled Windows client proxy', () => {
  const execute = (_file, args) => args.at(-1) === 'ProxyEnable'
    ? 'ProxyEnable    REG_DWORD    0x1\r\n'
    : 'ProxyServer    REG_SZ    http=127.0.0.1:8080;https=127.0.0.1:7890\r\n';
  assert.equal(readWindowsClientProxy(execute), 'http://127.0.0.1:7890/');
});

test('ignores a disabled Windows client proxy', () => {
  const execute = () => 'ProxyEnable    REG_DWORD    0x0\r\n';
  assert.equal(readWindowsClientProxy(execute), null);
});

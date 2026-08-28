import { execFileSync } from 'node:child_process';

const ENV_PROXY_KEYS = [
  'OH_MY_EXAM_PROXY',
  'HTTPS_PROXY',
  'https_proxy',
  'HTTP_PROXY',
  'http_proxy',
];

export function normalizeProxyUrl(value) {
  if (!value?.trim()) return null;
  const entries = value.trim().split(';').map((entry) => entry.trim()).filter(Boolean);
  const protocolEntries = new Map();
  const standalone = [];
  entries.forEach((entry) => {
    const separator = entry.indexOf('=');
    if (separator > 0) protocolEntries.set(entry.slice(0, separator).toLowerCase(), entry.slice(separator + 1));
    else standalone.push(entry);
  });
  const candidate = protocolEntries.get('https') || protocolEntries.get('http') || standalone[0];
  if (!candidate) return null;
  const withProtocol = /^[a-z][a-z\d+.-]*:\/\//i.test(candidate) ? candidate : `http://${candidate}`;
  try {
    const url = new URL(withProtocol);
    return ['http:', 'https:'].includes(url.protocol) ? url.href : null;
  } catch {
    return null;
  }
}

function queryWindowsInternetSetting(name, execute) {
  try {
    const output = execute(
      'reg.exe',
      ['query', 'HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Internet Settings', '/v', name],
      { encoding: 'utf8', windowsHide: true, stdio: ['ignore', 'pipe', 'ignore'] },
    );
    return output.match(new RegExp(`${name}\\s+REG_\\w+\\s+(.+)$`, 'mi'))?.[1]?.trim() || null;
  } catch {
    return null;
  }
}

export function readWindowsClientProxy(execute = execFileSync) {
  const enabled = queryWindowsInternetSetting('ProxyEnable', execute);
  if (!enabled || Number.parseInt(enabled, 0) !== 1) return null;
  return normalizeProxyUrl(queryWindowsInternetSetting('ProxyServer', execute));
}

export function resolveClientProxyUrl({ env = process.env, platform = process.platform, execute = execFileSync } = {}) {
  for (const key of ENV_PROXY_KEYS) {
    const proxy = normalizeProxyUrl(env[key]);
    if (proxy) return proxy;
  }
  return platform === 'win32' ? readWindowsClientProxy(execute) : null;
}

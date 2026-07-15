import * as Network from 'expo-network';

const PORT = 5000;
const PING_TIMEOUT_MS = 350;
const CONCURRENCY = 32;

async function fetchPing(ip, timeoutMs) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(`http://${ip}:${PORT}/ping`, { signal: controller.signal });
    if (!res.ok) return false;
    const data = await res.json();
    return data && data.app === 'remote-control';
  } catch {
    return false;
  } finally {
    clearTimeout(timer);
  }
}

export async function verifyServer(ip, timeoutMs = 2500) {
  return fetchPing(ip, timeoutMs);
}

export async function discoverServer() {
  const myIp = await Network.getIpAddressAsync();
  if (!myIp || myIp === '0.0.0.0') return null;

  const parts = myIp.split('.');
  const base = parts.slice(0, 3).join('.');
  const myLast = Number(parts[3]);

  const hosts = [];
  for (let i = 1; i <= 254; i++) {
    if (i !== myLast) hosts.push(`${base}.${i}`);
  }

  for (let start = 0; start < hosts.length; start += CONCURRENCY) {
    const batch = hosts.slice(start, start + CONCURRENCY);
    const results = await Promise.all(
      batch.map(async (ip) => ((await fetchPing(ip, PING_TIMEOUT_MS)) ? ip : null))
    );
    const found = results.find(Boolean);
    if (found) return found;
  }
  return null;
}

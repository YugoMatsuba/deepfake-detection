import { jest, describe, it, beforeAll, afterAll, expect } from '@jest/globals';
import { spawn } from 'child_process';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const repoRoot = path.resolve(__dirname, '../../..');
const backendDir = path.join(repoRoot, 'backend');

let serverProcess;
const BASE_URL = 'http://127.0.0.1:6001';

jest.setTimeout(120000);

async function waitForHealthcheck(timeoutMs = 60000) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    try {
      const res = await fetch(`${BASE_URL}/api/health`);
      if (res.ok) return true;
    } catch (err) {
      // Server not ready yet, continue polling
    }
    await new Promise((resolve) => setTimeout(resolve, 300));
  }
  throw new Error('Backend server did not become ready in time');
}

describe('FE↔API integration', () => {
  beforeAll(async () => {
    serverProcess = spawn('python', ['app.py'], {
      cwd: backendDir,
      env: {
        ...process.env,
        FLASK_APP: 'app.py',
        PORT: '6001',
        DATABASE_URL: 'sqlite:///instance/fe_integration.db',
        DB_BOOTSTRAP: '1',
      },
      stdio: 'inherit',
    });

    await waitForHealthcheck();
  }, 30000);

  afterAll(async () => {
    if (serverProcess) {
      await new Promise((resolve) => {
        serverProcess.once('close', resolve);
        serverProcess.kill();
      });
    }
  });

  it('returns healthcheck OK', async () => {
    const res = await fetch(`${BASE_URL}/api/health`);
    expect(res.status).toBe(200);
    const data = await res.json();
    expect(data).toEqual({ ok: true });
  });
});

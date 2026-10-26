import { logRequests } from 'next/dist/server/dev/log-requests';
import config from '../next.config';

test('Next development logs omit OAuth queries while retaining ordinary page requests', () => {
  let output = '';
  const writer = jest.spyOn(process.stdout, 'write').mockImplementation((text) => {
    output += text;
    return true;
  });
  try {
    for (const query of [
      'code=synthetic-code-sentinel&state=synthetic-state-sentinel',
      'error=access_denied&state=synthetic-state-sentinel',
    ]) {
      logRequests({ method: 'GET', url: `/api/v1/auth/github/callback?${query}` },
        { statusCode: 303 }, config.logging, 0n, 1000000n);
    }
    expect(output).toBe('');
    logRequests({ method: 'GET', url: '/workspace' }, { statusCode: 200 },
      config.logging, 0n, 1000000n);
    expect(output).toContain('/workspace');
    expect(output).not.toContain('synthetic-');
  } finally {
    writer.mockRestore();
  }
});

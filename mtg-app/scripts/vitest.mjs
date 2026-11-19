// Runs Vitest from an upper-case drive path on Windows.
//
// When the shell's cwd is "c:\..." (lower-case drive, as VS Code's terminal
// often has), Vitest's workers load its runner from "c:/..." while the test
// file's `import 'vitest'` resolves through realpath to "C:/...". The two
// copies don't share state and every describe() fails with "Cannot read
// properties of undefined (reading 'config')". Starting Vitest with a
// normalised cwd and entry path keeps a single spelling.
import { spawn } from 'node:child_process';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const upper = p => p.replace(/^[a-z]:/, d => d.toUpperCase());
const root = upper(resolve(dirname(fileURLToPath(import.meta.url)), '..'));
const cli = resolve(root, 'node_modules', 'vitest', 'vitest.mjs');

const child = spawn(process.execPath, [cli, ...process.argv.slice(2)], { cwd: root, stdio: 'inherit' });
child.on('exit', (code, signal) => {
  if (signal != null) {
    process.kill(process.pid, signal);
  } else {
    process.exit(code ?? 1);
  }
});

#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';

const root = path.resolve(process.cwd(), 'src');
const allow = [
  /\.test\./,
  /\.spec\./,
  /\/__tests__\//,
  /\/stories\//,
  /src\/components\/backtest\/MonteCarloChart\.tsx$/,
  /src\/components\/charts\/ChartA11y\.tsx$/,
  /src\/components\/connect\/BrokerCard\.tsx$/,
  /src\/pages\/MarketEducation\.tsx$/,
  /src\/pages\/portfolio\/PortfolioOptions\.tsx$/,
];

const hits = [];

// The allow-list regexes are POSIX-style (forward slashes) but path.join
// emits backslashes on Windows. Normalize before matching so the check
// produces identical results on every platform.
const toPosix = (p) => (path.sep === '/' ? p : p.split(path.sep).join('/'));

const walk = (dir) => {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      walk(full);
      continue;
    }
    if (!/\.(ts|tsx|js|jsx)$/.test(entry.name)) continue;
    const fullPosix = toPosix(full);
    if (allow.some((re) => re.test(fullPosix))) continue;
    const content = fs.readFileSync(full, 'utf8');
    if (/\$\d+/.test(content)) hits.push(full);
  }
};

walk(root);

if (hits.length > 0) {
  console.error('Hardcoded USD prices found:');
  for (const hit of hits) console.error(` - ${path.relative(process.cwd(), hit)}`);
  process.exit(1);
}

console.log('No hardcoded USD prices found.');

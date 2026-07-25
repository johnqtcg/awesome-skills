'use strict';
// Plain Node test runner — no dependencies, exits non-zero on failure.
// Run: node security_examples.test.js

const crypto = require('node:crypto');
const { safeTokenEqual, safeFixedWidthEqual, isPublicAddress } = require('./security_examples');

let failures = 0;
function check(label, cond) {
  if (cond) {
    console.log(`  ok   ${label}`);
  } else {
    console.error(`  FAIL ${label}`);
    failures++;
  }
}

console.log('timingSafeEqual: raw-buffer misuse actually throws (the bug being prevented)');
{
  let threw = false;
  try {
    crypto.timingSafeEqual(Buffer.from('abc'), Buffer.from('abcd'));
  } catch (e) {
    threw = e instanceof RangeError;
  }
  check('raw timingSafeEqual throws RangeError on length mismatch', threw);
}

console.log('safeTokenEqual: correct results, never throws');
{
  const stored = 's3cr3t-token';
  const cases = [
    ['exact match', stored, true],
    ['same length, wrong', 's3cr3t-tokeX', false],
    ['shorter', 's3', false],
    ['longer', stored + 'AAAAAAAA', false],
    ['empty', '', false],
  ];
  for (const [label, provided, want] of cases) {
    let got;
    try {
      got = safeTokenEqual(provided, stored);
    } catch (e) {
      got = `threw ${e.constructor.name}`;
    }
    check(`safeTokenEqual(${label}) === ${want}`, got === want);
  }
  check('safeTokenEqual(null) === false (no throw)', safeTokenEqual(null, stored) === false);
  check('safeFixedWidthEqual(shorter) === false (no throw)', safeFixedWidthEqual('s3', stored) === false);
  check('safeFixedWidthEqual(exact) === true', safeFixedWidthEqual(stored, stored) === true);
}

console.log('isPublicAddress: blocks every internal range');
{
  const mustBlock = [
    '127.0.0.1', '10.0.0.1', '172.16.0.1', '172.31.255.255', '192.168.1.1',
    '169.254.169.254', '0.0.0.0', '100.64.0.1',
    '::1', 'fd00::1', 'fe80::1', '::ffff:127.0.0.1', '::ffff:169.254.169.254',
  ];
  const mustAllow = ['8.8.8.8', '1.1.1.1', '93.184.216.34', '172.32.0.1', '172.15.0.1', '2606:4700::1111'];
  for (const ip of mustBlock) check(`blocks ${ip}`, isPublicAddress(ip) === false);
  for (const ip of mustAllow) check(`allows ${ip}`, isPublicAddress(ip) === true);
}

if (failures > 0) {
  console.error(`\n${failures} check(s) failed`);
  process.exit(1);
}
console.log('\nall node security example checks passed');

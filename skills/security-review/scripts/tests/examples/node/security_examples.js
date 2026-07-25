'use strict';
// GOOD Node patterns from references/lang-nodejs.md, as real runnable code.
// A security reference whose examples are never executed drifts into being wrong.

const crypto = require('node:crypto');
const net = require('node:net');

// --- Constant-time token comparison -----------------------------------------
// crypto.timingSafeEqual THROWS RangeError when byte lengths differ. Since the supplied
// token is attacker-controlled, calling it on raw buffers turns any wrong-length token
// into an unhandled exception (500 / crash), not a rejection.

// Hashing normalises length, so unequal inputs can never throw and the supplied token's
// length is not revealed by an early return.
function safeTokenEqual(provided, stored) {
  if (typeof provided !== 'string') return false;
  const a = crypto.createHash('sha256').update(provided, 'utf8').digest();
  const b = crypto.createHash('sha256').update(stored, 'utf8').digest();
  return crypto.timingSafeEqual(a, b);
}

// Acceptable when both sides are guaranteed fixed-width: check length FIRST, never throw.
function safeFixedWidthEqual(provided, stored) {
  const a = Buffer.from(provided, 'utf8');
  const b = Buffer.from(stored, 'utf8');
  if (a.length !== b.length) return false; // leaks length only, not content
  return crypto.timingSafeEqual(a, b);
}

// --- SSRF address classification --------------------------------------------
// Every resolved A/AAAA record must be checked, not just the first.
function isPublicAddress(ip) {
  const v = net.isIP(ip) === 6 && ip.startsWith('::ffff:') ? ip.slice(7) : ip; // unmap
  if (net.isIP(v) === 4) {
    const [a, b] = v.split('.').map(Number);
    if (
      a === 10 ||
      a === 127 ||
      a === 0 ||
      (a === 172 && b >= 16 && b <= 31) ||
      (a === 192 && b === 168) ||
      (a === 169 && b === 254) || // link-local incl. cloud IMDS
      (a === 100 && b >= 64 && b <= 127) // CGNAT
    ) {
      return false;
    }
    return true;
  }
  const lower = v.toLowerCase();
  return !(
    lower === '::1' ||
    lower.startsWith('fc') ||
    lower.startsWith('fd') ||
    lower.startsWith('fe80')
  );
}

module.exports = { safeTokenEqual, safeFixedWidthEqual, isPublicAddress };

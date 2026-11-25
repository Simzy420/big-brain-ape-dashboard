import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { test } from 'node:test';

test('positions.json schema', () => {
  const p = JSON.parse(readFileSync('data/positions.json', 'utf8'));
  assert.equal(typeof p.accountValue, 'number');
  assert.equal(typeof p.withdrawable, 'number');
  assert.equal(typeof p.totalUnrealizedPnl, 'number');
  assert.equal(typeof p.totalMarginUsed, 'number');
  assert.equal(typeof p.availableCash, 'number');
  assert.ok(Array.isArray(p.positions), 'positions is array');
  assert.equal(p.positions.length, 1, '1 position');
  const pos = p.positions[0];
  assert.equal(typeof pos.symbol, 'string');
  assert.equal(pos.rawToken, 'xyz:GOLD');
  assert.equal(pos.side, 'LONG');
  assert.equal(typeof pos.size, 'number');
  assert.equal(pos.size, 0.20, 'size is 0.20');
  assert.equal(typeof pos.entryPrice, 'number');
  assert.equal(typeof pos.currentPrice, 'number');
  assert.equal(typeof pos.unrealizedPnl, 'number');
  assert.equal(typeof pos.pnlPercent, 'number');
  assert.equal(typeof pos.marginUsed, 'number');
  assert.equal(typeof pos.leverage, 'number');
  assert.equal(typeof pos.marginType, 'string');
  assert.equal(typeof pos.positionValue, 'number');
  assert.equal(typeof pos.stopLoss, 'number');
  assert.equal(typeof pos.tvSymbol, 'string');
  assert.ok(Array.isArray(p.pieValueSlices), 'pieValueSlices array');
  assert.ok(Array.isArray(p.pieMarginSlices), 'pieMarginSlices array');
  assert.equal(typeof p.generatedAt, 'string');
  assert.equal(typeof p.timestamp, 'number');
  assert.ok(p.accountValue > 1000, 'account value reasonable');
  assert.ok(pos.marginUsed < p.accountValue, 'margin < account value');
});

test('snapshot.json schema', () => {
  const s = JSON.parse(readFileSync('data/snapshot.json', 'utf8'));
  assert.equal(typeof s.date, 'string');
  assert.ok(s.date.includes('November 25, 2026'), 'date is current');
  assert.equal(typeof s.assets, 'object');
  assert.ok(s.assets['S&P 500'], 'S&P 500 present');
  assert.ok(s.assets.NASDAQ, 'NASDAQ present');
  assert.ok(s.assets.BTC, 'BTC present');
  assert.equal(typeof s.risk_score, 'number');
  assert.equal(typeof s.risk_bias, 'string');
  assert.ok(s.risk_bias.includes('RISK'), 'risk_bias set');
  assert.equal(typeof s.fear_greed, 'object');
  assert.equal(typeof s.metrics, 'object');
  assert.ok(s.metrics.vix, 'VIX present');
  assert.ok(s.metrics.yield_10y, '10Y present');
  assert.ok(s.metrics.dxy, 'DXY present');
  assert.ok(s.metrics.gold, 'gold present');
  assert.ok(Array.isArray(s.signals), 'signals array');
  assert.ok(s.signals.length >= 3, 'multiple signals');
  for (const sig of s.signals) {
    assert.ok(sig.label, 'signal has label');
    assert.ok(sig.text, 'signal has text');
    assert.ok(sig.type, 'signal has type');
  }
  assert.equal(typeof s.history, 'object');
});

test('latest-state.json schema', () => {
  const st = JSON.parse(readFileSync('latest-state.json', 'utf8'));
  assert.equal(typeof st.lastRun, 'string');
  assert.ok(st.lastRun.includes('2026-11-25'), 'lastRun current');
  assert.equal(typeof st.accountValueUsd, 'number');
  assert.ok(Array.isArray(st.positions), 'positions array');
  assert.equal(typeof st.macroView, 'object');
  assert.ok(st.macroView.regime, 'regime set');
  assert.ok(Array.isArray(st.decisions), 'decisions array');
  assert.ok(st.decisions.length > 0, 'decisions present');
  assert.equal(typeof st.freshMindAudit, 'object');
  assert.ok(Object.keys(st.freshMindAudit).length >= 5, 'fresh-mind audit complete');
});

test('workspace latest-state.json schema', () => {
  const st = JSON.parse(readFileSync('../latest-state.json', 'utf8'));
  assert.equal(typeof st.lastRun, 'string');
  assert.ok(st.lastRun.includes('2026-11-25'), 'lastRun current');
  assert.ok(st.portfolio, 'portfolio present');
  assert.equal(typeof st.portfolio.accountValueUsd, 'number');
  assert.ok(Array.isArray(st.portfolio.positions), 'positions array');
  assert.ok(Array.isArray(st.closedThisRun), 'closedThisRun array');
  assert.equal(typeof st.decision, 'string');
});
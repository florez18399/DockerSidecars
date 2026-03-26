const express = require('express');
const app = express();
const PORT = process.env.PORT || 8080;
const APP_NAME = process.env.APP_NAME || 'mock-app';
const ZONE_ID = process.env.ZONE_ID || 'unknown-zone';
const SCENARIO = process.env.SCENARIO || 'NORMAL'; // NORMAL, DEGRADED, CHAOS, BURSTY

app.use(express.json());

// --- Configuration Constants ---
const ERROR_RATE = parseFloat(process.env.ERROR_RATE || '0.05'); // 5% default error rate
const LATENCY_BASE = parseInt(process.env.LATENCY_BASE || '100');
const LATENCY_VARIANCE = parseInt(process.env.LATENCY_VARIANCE || '200');

// --- Mock Data ---
let mockProducts = [
  { id: 1, name: `${APP_NAME} Item A`, category: 'Electronics', price: 100 },
  { id: 2, name: `${APP_NAME} Item B`, category: 'Homeware', price: 20 },
  { id: 3, name: `${APP_NAME} Item C`, category: 'Apparel', price: 50 }
];

// --- Behavior Middleware ---
const behaviorMiddleware = (req, res, next) => {
  let latency = LATENCY_BASE + Math.floor(Math.random() * LATENCY_VARIANCE);
  let shouldFail = Math.random() < ERROR_RATE;

  // Scenario Overrides
  switch (SCENARIO.toUpperCase()) {
    case 'DEGRADED':
      latency += 3000; // Extra 3s latency
      break;
    case 'CHAOS':
      shouldFail = Math.random() < 0.5; // 50% failure rate
      latency = 50; // Fast failures
      break;
    case 'BURSTY':
      // 10% chance of a massive spike
      if (Math.random() < 0.1) latency += 5000;
      break;
  }

  if (shouldFail && !req.path.includes('health')) {
    return setTimeout(() => {
      console.log(`[${ZONE_ID}/${APP_NAME}] [FAILURE] ${req.method} ${req.path} - Scenario: ${SCENARIO}`);
      res.status(500).json({ error: 'Internal Server Error', scenario: SCENARIO, app: APP_NAME });
    }, latency / 2);
  }

  setTimeout(next, latency);
};

app.use(behaviorMiddleware);

// --- Routes ---
const router = express.Router();

router.get('/', (req, res) => {
  res.json({ message: `Welcome to ${APP_NAME}`, zone: ZONE_ID, scenario: SCENARIO });
});

router.get('/products', (req, res) => {
  console.log(`[${ZONE_ID}/${APP_NAME}] Listing products`);
  res.json(mockProducts);
});

router.get('/api/health', (req, res) => {
  res.json({ status: 'UP', app: APP_NAME, zone: ZONE_ID });
});

router.get('/api/error', (req, res) => {
  res.status(500).json({ status: 'CRITICAL', message: 'Simulated endpoint error' });
});

const APP_PATH = process.env.APP_PATH || `/${APP_NAME}`;
app.use(APP_PATH, router);

app.listen(PORT, () => {
  console.log(`🚀 ${APP_NAME} (${SCENARIO}) listening on port ${PORT} at path ${APP_PATH}`);
});

/**
 * Simple proxy server to invoke AgentCore Runtime
 * Uses Python boto3 via child_process to call the runtime
 */
require('dotenv').config();
const express = require('express');
const cors = require('cors');
const { spawn } = require('child_process');
const path = require('path');

const app = express();
const PORT = 8080;

// Middleware
app.use(cors());
app.use(express.json());

// Get configuration from environment
const AGENT_RUNTIME_ARN = process.env.VITE_AGENT_RUNTIME_ARN || '';
const AWS_REGION = process.env.VITE_AWS_REGION || 'us-east-1';

console.log('🚀 Proxy Server Configuration:');
console.log('   Runtime ARN:', AGENT_RUNTIME_ARN);
console.log('   Region:', AWS_REGION);

if (!AGENT_RUNTIME_ARN) {
  console.error('❌ Error: VITE_AGENT_RUNTIME_ARN not set in .env file');
  process.exit(1);
}

/**
 * POST /invoke - Invoke the AgentCore Runtime using Python
 */
app.post('/invoke', async (req, res) => {
  try {
    const { prompt } = req.body;
    const authToken = req.headers.authorization?.replace('Bearer ', '');

    if (!prompt) {
      return res.status(400).json({ error: 'Prompt is required' });
    }

    if (!authToken) {
      return res.status(401).json({ error: 'Authorization token is required' });
    }

    console.log(`📨 Invoking runtime with prompt: ${prompt.substring(0, 50)}...`);

    // Create Python script path
    const pythonScript = path.join(__dirname, 'invoke_runtime.py');

    // Spawn Python process
    const python = spawn('python3', [
      pythonScript,
      AGENT_RUNTIME_ARN,
      AWS_REGION,
      authToken,
      prompt
    ]);

    let output = '';
    let errorOutput = '';

    python.stdout.on('data', (data) => {
      output += data.toString();
    });

    python.stderr.on('data', (data) => {
      errorOutput += data.toString();
      console.error('Python stderr:', data.toString());
    });

    python.on('close', (code) => {
      if (code !== 0) {
        console.error(`❌ Python process exited with code ${code}`);
        console.error('Error output:', errorOutput);
        return res.status(500).json({
          error: 'Failed to invoke runtime',
          details: errorOutput,
        });
      }

      try {
        const result = JSON.parse(output);
        console.log(`✅ Response received: ${result.response?.substring(0, 50)}...`);
        res.json(result);
      } catch (e) {
        console.error('❌ Failed to parse Python output:', e);
        console.error('Output was:', output);
        res.status(500).json({
          error: 'Failed to parse response',
          details: output,
        });
      }
    });

  } catch (error) {
    console.error('❌ Error invoking runtime:', error);
    res.status(500).json({
      error: error.message || 'Failed to invoke runtime',
      details: error.toString(),
    });
  }
});

/**
 * GET /health - Health check
 */
app.get('/health', (req, res) => {
  res.json({
    status: 'ok',
    runtimeArn: AGENT_RUNTIME_ARN,
    region: AWS_REGION,
  });
});

// Start server
app.listen(PORT, () => {
  console.log(`\n✅ Proxy server running on http://localhost:${PORT}`);
  console.log(`   Health check: http://localhost:${PORT}/health`);
  console.log(`   Invoke endpoint: http://localhost:${PORT}/invoke\n`);
});

#!/usr/bin/env node
/**
 * supabase_sse_bridge.mjs — SSE bridge for Supabase MCP
 * 
 * Creates a proper MCP SSE server using @modelcontextprotocol/sdk.
 * Internally proxies tool calls to the stdio Supabase MCP server.
 * 
 * Start:  node mcp-server-supabase/supabase_sse_bridge.mjs
 * 
 * Endpoints:
 *   GET  /sse       → SSE stream (MCP clients connect here)
 *   POST /messages  → JSON-RPC messages
 *   POST /query     → Simple REST: { "sql": "..." } → { "rows": [...] }
 *   GET  /health    → Health check
 */
import { spawn } from 'child_process';
import { createInterface } from 'readline';
import { readFileSync } from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { SSEServerTransport } from '@modelcontextprotocol/sdk/server/sse.js';
import express from 'express';
import { z } from 'zod';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PORT = 3100;

// ── Load token ──────────────────────────────────────────────────────────────
const envFile = readFileSync(path.join(__dirname, '..', '.env'), 'utf-8');
const token = envFile.match(/SUPABASE_ACCESS_TOKEN=(.*)/)?.[1]?.trim();
if (!token) { console.error('Missing SUPABASE_ACCESS_TOKEN in .env'); process.exit(1); }

const PROJECT_REF = 'rvjuymgbarospuwkkxhc';
const SERVER_PATH = path.join(__dirname, 'dist/transports/stdio.js');

// ── Stdio MCP subprocess ────────────────────────────────────────────────────
let mcpProcess = null;
let mcpReady = false;
let msgId = 1;
const pending = new Map();

function spawnStdio() {
    mcpProcess = spawn('node', [SERVER_PATH, '--project-ref', PROJECT_REF], {
        env: { ...process.env, SUPABASE_ACCESS_TOKEN: token },
        stdio: ['pipe', 'pipe', 'pipe']
    });

    createInterface({ input: mcpProcess.stdout }).on('line', line => {
        try {
            const msg = JSON.parse(line);
            if (msg.id && pending.has(msg.id)) pending.get(msg.id)(msg);
        } catch { }
    });

    mcpProcess.stderr.on('data', d => {
        const txt = d.toString().trim();
        if (txt) console.error('[stdio]', txt);
    });

    mcpProcess.on('exit', code => {
        console.log(`Stdio MCP exited (${code}), respawning...`);
        mcpReady = false;
        setTimeout(spawnStdio, 2000);
    });
}

function stdioRpc(method, params) {
    return new Promise((resolve, reject) => {
        const id = msgId++;
        pending.set(id, resolve);
        mcpProcess.stdin.write(JSON.stringify({ jsonrpc: '2.0', id, method, params }) + '\n');
        setTimeout(() => { pending.delete(id); reject(new Error('timeout')); }, 30000);
    });
}

async function initStdio() {
    await stdioRpc('initialize', {
        protocolVersion: '2024-11-05',
        capabilities: {},
        clientInfo: { name: 'sse-bridge', version: '1.0' }
    });
    mcpReady = true;
    console.log('✅ Stdio MCP initialized');
}

function parseRows(response) {
    const text = response.result?.content?.[0]?.text || '';
    const unescaped = text.replace(/\\n/g, '\n').replace(/\\"/g, '"');
    const start = unescaped.indexOf('[');
    const end = unescaped.lastIndexOf(']');
    if (start !== -1 && end > start) {
        try { return JSON.parse(unescaped.substring(start, end + 1)); } catch { }
    }
    return [];
}

// ── MCP Server (SSE-facing) ─────────────────────────────────────────────────
const mcpServer = new McpServer({
    name: 'supabase-linkedin',
    version: '1.0.0'
}, {
    capabilities: {
        tools: {}
    }
});

// Register tools that proxy to stdio
mcpServer.tool(
    'execute_sql',
    'Run SQL queries (SELECT/INSERT/UPDATE/DELETE) against linkedin_hunter schema',
    { query: z.string().describe('SQL query. Always prefix tables with linkedin_hunter.') },
    async ({ query }) => {
        const r = await stdioRpc('tools/call', { name: 'execute_sql', arguments: { query } });
        const text = r.result?.content?.[0]?.text || 'No result';
        return { content: [{ type: 'text', text }] };
    }
);

mcpServer.tool(
    'apply_migration',
    'Run DDL (CREATE/ALTER/DROP). Name must be globally unique.',
    {
        name: z.string().describe('Unique migration name'),
        query: z.string().describe('DDL SQL. End with NOTIFY pgrst, reload schema;')
    },
    async ({ name, query }) => {
        const r = await stdioRpc('tools/call', { name: 'apply_migration', arguments: { name, query } });
        const text = r.result?.content?.[0]?.text || 'No result';
        return { content: [{ type: 'text', text }] };
    }
);

mcpServer.tool(
    'list_tables',
    'List all tables with columns, types, and row counts',
    { schemas: z.array(z.string()).default(['linkedin_hunter']) },
    async ({ schemas }) => {
        const r = await stdioRpc('tools/call', { name: 'list_tables', arguments: { schemas } });
        const text = r.result?.content?.[0]?.text || 'No result';
        return { content: [{ type: 'text', text }] };
    }
);

// ── Express + SSE ───────────────────────────────────────────────────────────
const app = express();
app.use(express.json());

const transports = new Map();

app.get('/sse', async (req, res) => {
    const transport = new SSEServerTransport('/messages', res);
    transports.set(transport.sessionId, transport);
    console.log(`SSE client connected: ${transport.sessionId}`);
    await mcpServer.connect(transport);
});

app.post('/messages', (req, res) => {
    const sessionId = req.query.sessionId;
    if (!sessionId) return res.status(400).json({ error: 'sessionId required' });
    const transport = transports.get(sessionId);
    if (transport) {
        transport.handlePostMessage(req, res);
    } else {
        res.status(404).json({ error: 'session not found' });
    }
});

// Simple REST endpoint for quick queries
app.post('/query', async (req, res) => {
    if (!mcpReady) return res.status(503).json({ error: 'MCP not ready' });
    const sql = req.body.sql || req.body.query;
    if (!sql) return res.status(400).json({ error: 'Missing sql field' });
    try {
        const isDDL = /^\s*(ALTER|CREATE|DROP)/i.test(sql);
        const toolName = isDDL ? 'apply_migration' : 'execute_sql';
        const args = isDDL ? { name: `rest_${Date.now()}`, query: sql } : { query: sql };
        const r = await stdioRpc('tools/call', { name: toolName, arguments: args });
        const rows = parseRows(r);
        res.json({ rows, count: rows.length });
    } catch (err) {
        res.status(500).json({ error: err.message });
    }
});

app.get('/health', (req, res) => {
    res.json({ status: mcpReady ? 'ok' : 'initializing', port: PORT });
});

// ── Boot ────────────────────────────────────────────────────────────────────
spawnStdio();
setTimeout(async () => {
    try {
        await initStdio();
        app.listen(PORT, '127.0.0.1', () => {
            console.log(`\n🟢 Supabase MCP SSE Bridge on http://localhost:${PORT}`);
            console.log(`   MCP SSE:   GET  http://localhost:${PORT}/sse`);
            console.log(`   Messages:  POST http://localhost:${PORT}/messages`);
            console.log(`   REST:      POST http://localhost:${PORT}/query`);
            console.log(`   Health:    GET  http://localhost:${PORT}/health\n`);
        });
    } catch (err) {
        console.error('Boot failed:', err);
        process.exit(1);
    }
}, 2000);

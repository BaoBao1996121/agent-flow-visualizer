#!/usr/bin/env node
/** Dependency-free Chrome DevTools screenshot helper (Node.js 22+). */

import { writeFileSync } from 'node:fs';

const [
    webSocketUrl,
    outputPath,
    targetUrl,
    widthArg = '1600',
    heightArg = '1000',
    evaluation = '',
] = process.argv.slice(2);
if (!webSocketUrl || !outputPath || !targetUrl) {
    console.error('Usage: node scripts/cdp_capture.mjs <ws-url> <output.png> <url> [width] [height]');
    process.exit(2);
}
if (typeof WebSocket === 'undefined') {
    console.error('This helper requires Node.js 22+ with a global WebSocket client.');
    process.exit(2);
}

const width = Number(widthArg);
const height = Number(heightArg);
const socket = new WebSocket(webSocketUrl);
const pending = new Map();
let nextId = 1;

function send(method, params = {}) {
    const id = nextId++;
    socket.send(JSON.stringify({ id, method, params }));
    return new Promise((resolve, reject) => pending.set(id, { resolve, reject, method }));
}

function wait(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

socket.addEventListener('message', event => {
    const message = JSON.parse(String(event.data));
    if (!message.id || !pending.has(message.id)) return;
    const request = pending.get(message.id);
    pending.delete(message.id);
    if (message.error) request.reject(new Error(`${request.method}: ${message.error.message}`));
    else request.resolve(message.result || {});
});

socket.addEventListener('error', event => {
    console.error('CDP WebSocket error', event.message || event.type);
    process.exitCode = 1;
});

socket.addEventListener('open', async () => {
    try {
        await send('Page.enable');
        await send('Runtime.enable');
        await send('Emulation.setDeviceMetricsOverride', {
            width,
            height,
            deviceScaleFactor: 1,
            mobile: false,
        });
        await send('Page.navigate', { url: targetUrl });

        const deadline = Date.now() + 15_000;
        while (Date.now() < deadline) {
            await wait(250);
            const check = await send('Runtime.evaluate', {
                expression: `Boolean(document.readyState === 'complete' && window.anthillApp && window.anthillApp.world)`,
                returnByValue: true,
            });
            if (check.result?.value) break;
        }
        if (evaluation) {
            await send('Runtime.evaluate', {
                expression: evaluation,
                awaitPromise: true,
                returnByValue: true,
            });
        }
        await wait(900);
        const screenshot = await send('Page.captureScreenshot', {
            format: 'png',
            fromSurface: true,
            captureBeyondViewport: false,
        });
        writeFileSync(outputPath, Buffer.from(screenshot.data, 'base64'));
        console.log(outputPath);
        socket.close();
    } catch (error) {
        console.error(error.stack || error.message);
        process.exitCode = 1;
        socket.close();
    }
});

/**
 * Data flow simulation - animate how data flows through the agent graph
 * Supports two modes:
 *   - "static": BFS traversal on the static graph (/api/simulate)
 *   - "trace":  Real runtime tracing via sys.settrace (/api/trace)
 */

let simulationState = {
    running: false,
    paused: false,
    currentStep: 0,
    traceSteps: [],
    intervalId: null,
    visitedNodes: new Set(),
    visitedEdges: new Set(),
    mode: 'static', // 'static' or 'trace'
};

/**
 * Get the current simulation mode from radio buttons
 */
function getSimMode() {
    const radio = document.querySelector('input[name="sim-mode"]:checked');
    return radio ? radio.value : 'static';
}

/**
 * Handle mode toggle UI
 */
function onSimModeChange() {
    const mode = getSimMode();
    document.getElementById('sim-static-options').style.display = mode === 'static' ? '' : 'none';
    document.getElementById('sim-trace-options').style.display = mode === 'trace' ? '' : 'none';

    // Enable/disable fields
    const traceArgs = document.getElementById('trace-args');
    const simInput = document.getElementById('sim-input');
    if (traceArgs) traceArgs.disabled = mode !== 'trace' || !lastAnalysisResult;
    if (simInput) simInput.disabled = mode !== 'static' || !lastAnalysisResult;
}

/**
 * Start the data flow simulation
 */
async function startSimulation() {
    if (!cy || !currentGraphData) return;

    const entrySelect = document.getElementById('entry-select');
    const entry = entrySelect.value;

    if (!entry) {
        setStatus('请先选择入口函数', 'warn');
        return;
    }

    // Use stored project path from last analysis instead of input field
    const projectPath = lastAnalysisResult ? lastAnalysisResult.project_dir : '';
    if (!projectPath) {
        setStatus('请先分析项目', 'warn');
        return;
    }

    const mode = getSimMode();
    simulationState.mode = mode;

    setStatus(mode === 'trace' ? '正在执行真实追踪...' : '正在计算模拟路径...', 'info');

    try {
        let traceSteps;

        if (mode === 'trace') {
            traceSteps = await fetchRealTrace(projectPath, entry);
        } else {
            traceSteps = await fetchStaticSimulation(projectPath, entry);
        }

        simulationState.traceSteps = traceSteps;
        simulationState.currentStep = 0;
        simulationState.running = true;
        simulationState.paused = false;
        simulationState.visitedNodes = new Set();
        simulationState.visitedEdges = new Set();

        // Clear previous simulation visuals and old timers
        if (simulationState.intervalId) {
            clearInterval(simulationState.intervalId);
            simulationState.intervalId = null;
        }
        cy.elements().removeClass('sim-active sim-visited');

        // Update button states
        document.getElementById('sim-btn').textContent = '⏸ 暂停';
        document.getElementById('sim-step-btn').disabled = false;
        document.getElementById('sim-reset-btn').disabled = false;

        // Start animation
        const speed = parseInt(document.getElementById('sim-speed').value);
        runSimulationStep();
        simulationState.intervalId = setInterval(runSimulationStep, speed);

        const label = mode === 'trace' ? '真实追踪' : '静态模拟';
        setStatus(`${label}进行中: ${traceSteps.length} 步`, 'info');

    } catch (error) {
        setStatus(`模拟失败: ${error.message}`, 'error');
    }
}

/**
 * Fetch static BFS simulation from /api/simulate
 */
async function fetchStaticSimulation(projectPath, entry) {
    const simInput = document.getElementById('sim-input');
    let inputData = {};
    try {
        const inputText = simInput.value.trim();
        if (inputText) inputData = JSON.parse(inputText);
    } catch {
        throw new Error('模拟输入必须是有效的 JSON 格式');
    }

    const response = await fetch('/api/simulate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            project_dir: projectPath,
            entry_point: entry,
            input_data: inputData,
        }),
    });

    if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || 'Simulation failed');
    }

    const result = await response.json();
    return result.trace; // array of step objects
}

/**
 * Fetch real runtime trace from /api/trace
 * Uses the node's filepath to correctly derive module and function name
 */
async function fetchRealTrace(projectPath, entryNodeId) {
    // Look up node data to get filepath
    const nodeData = currentGraphData
        ? currentGraphData.nodes.find(n => n.id === entryNodeId)
        : null;

    let entryModule, entryFunction;

    if (nodeData && nodeData.filepath) {
        // Derive module from filepath: "project_original\decry.py" → "project_original.decry"
        entryModule = nodeData.filepath
            .replace(/\\/g, '/')
            .replace(/\.py$/, '')
            .replace(/\//g, '.');

        // Function = node ID minus the module prefix
        // e.g. node ID "project_original.decry.request_encrpt", module "project_original.decry"
        //   → function "request_encrpt"
        const prefix = entryModule + '.';
        if (entryNodeId.startsWith(prefix)) {
            entryFunction = entryNodeId.slice(prefix.length);
        } else {
            // Fallback: last segment(s) after the module
            const parts = entryNodeId.split('.');
            const modParts = entryModule.split('.');
            entryFunction = parts.slice(modParts.length).join('.');
        }
    } else {
        // Fallback: guess from node ID (first segment as module)
        const parts = entryNodeId.split('.');
        if (parts.length < 2) {
            throw new Error('无法从节点ID推断模块和函数: ' + entryNodeId);
        }
        entryModule = parts[0];
        entryFunction = parts.slice(1).join('.');
    }

    if (!entryFunction) {
        throw new Error('无法推断入口函数: ' + entryNodeId);
    }

    // Parse trace args
    let traceArgs = [];
    try {
        const argsText = (document.getElementById('trace-args').value || '').trim();
        if (argsText) {
            traceArgs = JSON.parse(argsText);
            if (!Array.isArray(traceArgs)) {
                throw new Error('参数必须是数组');
            }
        }
    } catch (e) {
        throw new Error('函数参数必须是有效的 JSON 数组: ' + e.message);
    }

    const response = await fetch('/api/trace', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            project_dir: projectPath,
            entry_module: entryModule,
            entry_function: entryFunction,
            args: traceArgs,
        }),
    });

    if (!response.ok) {
        const err = await response.json();
        throw new Error(err.detail || 'Trace failed');
    }

    const result = await response.json();
    if (!result.success) {
        throw new Error(result.error || '追踪执行失败');
    }

    // Convert call_sequence to trace steps compatible with the animation
    // Enrich with duration and exception from full events
    const events = result.events || [];
    // Build a map: qualified_name -> { duration_ms, return_value, exception }
    const returnMap = {};
    for (const ev of events) {
        if (ev.event_type === 'return' && ev.duration_ms != null) {
            returnMap[ev.qualified_name] = {
                duration_ms: ev.duration_ms,
                return_value: ev.return_value,
            };
        }
        if (ev.event_type === 'exception') {
            if (!returnMap[ev.qualified_name]) returnMap[ev.qualified_name] = {};
            returnMap[ev.qualified_name].exception = ev.exception;
        }
    }

    const steps = result.call_sequence.map((call, i) => {
        const extra = returnMap[call.node_id] || {};
        return {
            step: i,
            node_id: call.node_id,
            node_type: _getNodeType(call.node_id),
            input_data: call.args || {},
            output_data: extra.return_value ? { return: extra.return_value } : {},
            edges_taken: [],
            duration_ms: extra.duration_ms || null,
            exception: extra.exception || null,
            is_real_trace: true,
        };
    });

    // Show total duration in status
    if (result.total_duration_ms) {
        setStatus(`追踪完成: ${steps.length} 步, 耗时 ${result.total_duration_ms.toFixed(1)}ms`, 'success');
    }

    // Fill in edges_taken based on actual call sequence pairs
    // If call[i] → call[i+1] has an edge in the static graph, link it
    if (currentGraphData) {
        const edgeSet = new Set(
            currentGraphData.edges.map(e => e.source + '|' + e.target)
        );
        for (let i = 0; i < steps.length - 1; i++) {
            const src = steps[i].node_id;
            const tgt = steps[i + 1].node_id;
            if (edgeSet.has(src + '|' + tgt)) {
                steps[i].edges_taken.push({
                    target: tgt,
                    edge_type: 'call',
                    condition: '',
                });
            }
        }
    }

    return steps;
}

/**
 * Look up node type from current graph data
 */
function _getNodeType(nodeId) {
    if (!currentGraphData) return 'process';
    const node = currentGraphData.nodes.find(n => n.id === nodeId);
    return node ? node.type : 'process';
}

/**
 * Execute one simulation step
 */
function runSimulationStep() {
    if (!simulationState.running || simulationState.paused) return;

    const { traceSteps, currentStep, visitedNodes, visitedEdges } = simulationState;

    if (currentStep >= traceSteps.length) {
        stopSimulation();
        setStatus('模拟完成 ✓', 'success');
        return;
    }

    const step = traceSteps[currentStep];

    // Remove previous active state
    cy.elements().removeClass('sim-active');

    // Mark current node as active
    const currentNode = cy.getElementById(step.node_id);
    if (currentNode.length > 0) {
        currentNode.addClass('sim-active');

        // Mark as visited
        if (visitedNodes.size > 0) {
            // Previous nodes become "visited"
            for (const nodeId of visitedNodes) {
                cy.getElementById(nodeId).addClass('sim-visited').removeClass('sim-active');
            }
        }
        visitedNodes.add(step.node_id);

        // Animate edges taken
        if (step.edges_taken) {
            for (const edgeTaken of step.edges_taken) {
                const edges = cy.edges().filter(e =>
                    e.data('source') === step.node_id && e.data('target') === edgeTaken.target
                );
                edges.addClass('sim-active');

                // Mark previously active edges as visited
                for (const edgeId of visitedEdges) {
                    const prevEdge = cy.getElementById(edgeId);
                    if (prevEdge.length > 0) {
                        prevEdge.addClass('sim-visited').removeClass('sim-active');
                    }
                }
                edges.forEach(e => visitedEdges.add(e.id()));
            }
        }

        // Center view on current node
        cy.animate({
            center: { eles: currentNode },
            duration: 300,
        });

        // Show step info
        showTraceStepInfo(step, currentStep, traceSteps.length);
    } else {
        // Node not in graph (e.g., from external call or filtered out)
        showTraceStepInfo(step, currentStep, traceSteps.length);
    }

    simulationState.currentStep++;
}

/**
 * Step through simulation one step at a time
 */
function stepSimulation() {
    if (!simulationState.running) return;

    // Pause auto-play
    if (simulationState.intervalId) {
        clearInterval(simulationState.intervalId);
        simulationState.intervalId = null;
    }
    simulationState.paused = true;
    document.getElementById('sim-btn').textContent = '▶ 继续';

    // Run one step
    simulationState.paused = false;
    runSimulationStep();
    simulationState.paused = true;
}

/**
 * Reset simulation
 */
function resetSimulation() {
    stopSimulation();
    cy.elements().removeClass('sim-active sim-visited');
    removeTraceStepInfo();
    setStatus('模拟已重置', 'info');
}

/**
 * Stop simulation
 */
function stopSimulation() {
    if (simulationState.intervalId) {
        clearInterval(simulationState.intervalId);
        simulationState.intervalId = null;
    }
    simulationState.running = false;
    simulationState.paused = false;

    document.getElementById('sim-btn').textContent = '▶ 开始追踪';
    document.getElementById('sim-step-btn').disabled = true;
}

/**
 * Show trace step information overlay and data panel
 */
function showTraceStepInfo(step, index, total) {
    removeTraceStepInfo();

    const typeLabels = {
        entry_point: '入口点',
        llm_call: 'LLM 调用',
        tool: '工具执行',
        decision: '决策分支',
        sub_agent: '子 Agent',
        output: '输出',
        process: '处理',
        data_transform: '数据处理',
    };

    const typeLabel = typeLabels[step.node_type] || step.node_type;
    const modeTag = step.is_real_trace ? ' 🔴 实时' : ' 🔵 静态';
    const durationTag = (step.is_real_trace && step.duration_ms != null) ? ` ⏱${step.duration_ms.toFixed(1)}ms` : '';
    const exceptionTag = step.exception ? ' ⚠️' : '';

    // Top overlay bar
    const div = document.createElement('div');
    div.className = 'trace-step' + (step.exception ? ' trace-step-error' : '');
    div.id = 'trace-step-overlay';
    div.innerHTML = `步骤 ${index + 1}/${total}: <strong>${_escapeHtml(step.node_id.split('.').slice(-2).join('.'))}</strong> (${typeLabel})${modeTag}${durationTag}${exceptionTag}`;
    document.getElementById('graph-container').appendChild(div);

    // Bottom data panel
    const panel = document.createElement('div');
    panel.className = 'trace-data-panel';
    panel.id = 'trace-data-panel';

    let bodyHtml;
    if (step.is_real_trace) {
        // Real trace mode — show args, duration, exception
        const durationHtml = step.duration_ms != null
            ? `<span class="trace-duration">${step.duration_ms.toFixed(1)}ms</span>`
            : '';
        const exceptionHtml = step.exception
            ? `<div class="trace-exception">⚠️ ${_escapeHtml(step.exception)}</div>`
            : '';
        const returnHtml = step.output_data && step.output_data.return
            ? `<div class="trace-data-section">
                    <div class="trace-data-title">📤 返回值</div>
                    <pre class="trace-data-json">${_escapeHtml(step.output_data.return)}</pre>
                </div>`
            : '';

        bodyHtml = `
            <div class="trace-data-row">
                <div class="trace-data-section">
                    <div class="trace-data-title">📥 调用参数 ${durationHtml}</div>
                    <pre class="trace-data-json">${_escapeHtml(JSON.stringify(step.input_data, null, 2))}</pre>
                </div>
                ${returnHtml}
                <div class="trace-data-section">
                    <div class="trace-data-title">📍 函数</div>
                    <pre class="trace-data-json">${_escapeHtml(step.node_id)}</pre>
                    ${exceptionHtml}
                </div>
            </div>
        `;
    } else {
        // Static simulation mode — show input/output + next edges
        const nextTargets = (step.edges_taken || []).map(e => {
            const shortTarget = e.target.split('.').slice(-2).join('.');
            return e.condition
                ? `<span class="trace-edge-cond">${_escapeHtml(shortTarget)}</span> <small>(${_escapeHtml(e.condition)})</small>`
                : `<span class="trace-edge-call">${_escapeHtml(shortTarget)}</span>`;
        }).join(' → ');

        bodyHtml = `
            <div class="trace-data-row">
                <div class="trace-data-section">
                    <div class="trace-data-title">📥 输入数据</div>
                    <pre class="trace-data-json">${_escapeHtml(JSON.stringify(step.input_data, null, 2))}</pre>
                </div>
                <div class="trace-data-section">
                    <div class="trace-data-title">📤 输出数据</div>
                    <pre class="trace-data-json">${_escapeHtml(JSON.stringify(step.output_data, null, 2))}</pre>
                </div>
                <div class="trace-data-section">
                    <div class="trace-data-title">➡️ 下一步</div>
                    <div class="trace-next">${nextTargets || '<em>终止</em>'}</div>
                </div>
            </div>
        `;
    }

    panel.innerHTML = bodyHtml;
    document.getElementById('graph-container').appendChild(panel);
}

/**
 * Remove trace step overlay and data panel
 */
function removeTraceStepInfo() {
    const existing = document.getElementById('trace-step-overlay');
    if (existing) existing.remove();
    const panel = document.getElementById('trace-data-panel');
    if (panel) panel.remove();
}

/**
 * Toggle simulation play/pause
 */
function toggleSimulation() {
    if (!simulationState.running) {
        startSimulation();
        return;
    }

    if (simulationState.paused) {
        // Resume
        simulationState.paused = false;
        const speed = parseInt(document.getElementById('sim-speed').value);
        simulationState.intervalId = setInterval(runSimulationStep, speed);
        document.getElementById('sim-btn').textContent = '⏸ 暂停';
    } else {
        // Pause
        simulationState.paused = true;
        if (simulationState.intervalId) {
            clearInterval(simulationState.intervalId);
            simulationState.intervalId = null;
        }
        document.getElementById('sim-btn').textContent = '▶ 继续';
    }
}

/**
 * Update simulation speed while running
 */
function onSpeedChange() {
    if (simulationState.running && !simulationState.paused && simulationState.intervalId) {
        clearInterval(simulationState.intervalId);
        const speed = parseInt(document.getElementById('sim-speed').value);
        simulationState.intervalId = setInterval(runSimulationStep, speed);
    }
}

// Wire up speed slider live update
document.addEventListener('DOMContentLoaded', function () {
    const slider = document.getElementById('sim-speed');
    if (slider) slider.addEventListener('input', onSpeedChange);
});

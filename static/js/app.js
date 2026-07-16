/**
 * Main application logic
 */

let lastAnalysisResult = null;

/**
 * Open native folder picker and fill the path input
 */
async function browseFolder() {
    const btn = document.getElementById('browse-btn');
    btn.disabled = true;
    try {
        const resp = await fetch('/api/browse');
        const data = await resp.json();
        if (data.path) {
            document.getElementById('project-path').value = data.path;
        }
    } catch (e) {
        console.error('Browse failed:', e);
    } finally {
        btn.disabled = false;
    }
}

/**
 * Analyze a Python agent project
 */
async function analyzeProject() {
    const pathInput = document.getElementById('project-path');
    const projectPath = pathInput.value.trim();

    if (!projectPath) {
        setStatus('请输入项目目录路径', 'error');
        pathInput.focus();
        return;
    }

    // Show loading
    document.getElementById('welcome').classList.add('hidden');
    document.getElementById('loading').classList.remove('hidden');
    setStatus('正在分析项目...', 'info');

    try {
        const response = await fetch('/api/analyze', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ project_dir: projectPath }),
        });

        if (!response.ok) {
            const err = await response.json();
            throw new Error(err.detail || `HTTP ${response.status}`);
        }

        const result = await response.json();
        lastAnalysisResult = result;

        // Reset simulation state from previous analysis
        if (simulationState.running) {
            resetSimulation();
        }

        // Render graph
        renderGraph(result.graph);

        // Update project info
        updateProjectInfo(result.graph.metadata, result.project_dir, result.warnings || []);

        // Update simulation controls
        updateSimControls(result.graph);

        // Update status
        const meta = result.graph.metadata;
        const warnings = result.warnings || [];
        let statusMsg = `分析完成: ${meta.displayed_nodes} 个节点, ${meta.displayed_edges} 条边`;
        if (warnings.length > 0) {
            statusMsg += ` (${warnings.length} 个文件解析警告)`;
        }
        setStatus(statusMsg, warnings.length > 0 ? 'warn' : 'success');
        document.getElementById('status-stats').textContent =
            `${meta.entry_points.length} 入口 | ${meta.llm_calls.length} LLM | ${meta.tools.length} 工具 | ${meta.decision_points.length} 决策`;

    } catch (error) {
        setStatus(`分析失败: ${error.message}`, 'error');

        // Clear stale state from previous successful analysis
        lastAnalysisResult = null;
        if (simulationState.running) {
            resetSimulation();
        }
        if (cy) {
            cy.elements().remove();
        }
        currentGraphData = null;
        _moduleCollapsed = false;
        disableSimControls();

        // Reset all UI panels
        document.getElementById('project-info').innerHTML = '<p class=\"placeholder\">分析项目后显示信息</p>';
        const statsEl = document.getElementById('graph-stats');
        if (statsEl) statsEl.style.display = 'none';
        const modulePanel = document.getElementById('module-filter-panel');
        if (modulePanel) modulePanel.style.display = 'none';
        document.getElementById('layout-btn').disabled = true;
        document.getElementById('fit-btn').disabled = true;
        document.getElementById('export-btn').disabled = true;
        document.getElementById('layout-select').disabled = true;
        document.getElementById('status-stats').textContent = '';
        _stopMinimap();

        document.getElementById('welcome').classList.remove('hidden');
    } finally {
        document.getElementById('loading').classList.add('hidden');
    }
}

/**
 * Update the project info panel
 */
function updateProjectInfo(metadata, projectDir, warnings) {
    const infoDiv = document.getElementById('project-info');

    let frameworksHtml = '';
    if (metadata.detected_frameworks && metadata.detected_frameworks.length > 0) {
        frameworksHtml = `
            <div style="margin-bottom: 8px;">
                ${metadata.detected_frameworks.map(f => `<span class="framework-tag">${_escapeHtml(f)}</span>`).join(' ')}
            </div>
        `;
    }

    let warningsHtml = '';
    if (warnings && warnings.length > 0) {
        warningsHtml = `
            <div style="margin-top: 8px; padding: 6px 8px; background: rgba(255,158,100,0.1); border: 1px solid var(--accent-orange); border-radius: 4px;">
                <div style="font-size: 11px; color: var(--accent-orange); font-weight: 600; margin-bottom: 4px;">⚠ 解析警告 (${warnings.length})</div>
                ${warnings.map(w => `<div style="font-size: 10px; color: var(--text-muted); margin-bottom: 2px;">${_escapeHtml(w)}</div>`).join('')}
            </div>
        `;
    }

    infoDiv.innerHTML = `
        ${frameworksHtml}
        <div class="info-stat">
            <span class="label">项目路径</span>
            <span class="value" title="${_escapeHtml(projectDir)}">${_escapeHtml(_shortenPath(projectDir))}</span>
        </div>
        <div class="info-stat">
            <span class="label">总函数数</span>
            <span class="value">${metadata.total_functions}</span>
        </div>
        <div class="info-stat">
            <span class="label">显示节点</span>
            <span class="value">${metadata.displayed_nodes}</span>
        </div>
        <div class="info-stat">
            <span class="label">连接边数</span>
            <span class="value">${metadata.displayed_edges}</span>
        </div>
        <div class="info-stat">
            <span class="label">入口点</span>
            <span class="value">${metadata.entry_points.length}</span>
        </div>
        <div class="info-stat">
            <span class="label">LLM 调用</span>
            <span class="value">${metadata.llm_calls.length}</span>
        </div>
        <div class="info-stat">
            <span class="label">工具数</span>
            <span class="value">${metadata.tools.length}</span>
        </div>
        <div class="info-stat">
            <span class="label">决策分支</span>
            <span class="value">${metadata.decision_points.length}</span>
        </div>
        ${warningsHtml}
    `;
}

/**
 * Update simulation controls
 */
function updateSimControls(graphData) {
    const entrySelect = document.getElementById('entry-select');
    const simInput = document.getElementById('sim-input');
    const simBtn = document.getElementById('sim-btn');

    // Populate entry points
    entrySelect.innerHTML = '';
    entrySelect.onchange = function () {
        if (this.value) focusNode(this.value);
    };

    // First add detected entry points
    const entryPoints = graphData.metadata.entry_points || [];
    if (entryPoints.length > 0) {
        const group = document.createElement('optgroup');
        group.label = '检测到的入口点';
        for (const ep of entryPoints) {
            const opt = document.createElement('option');
            opt.value = ep;
            opt.textContent = _shortNodeId(ep);
            group.appendChild(opt);
        }
        entrySelect.appendChild(group);
    }

    // Then add all nodes as options
    const otherGroup = document.createElement('optgroup');
    otherGroup.label = '所有节点';
    for (const node of graphData.nodes) {
        if (!entryPoints.includes(node.id)) {
            const opt = document.createElement('option');
            opt.value = node.id;
            opt.textContent = `${_shortNodeId(node.id)} (${NODE_TYPE_LABELS[node.type] || node.type})`;
            otherGroup.appendChild(opt);
        }
    }
    entrySelect.appendChild(otherGroup);

    // Enable controls
    entrySelect.disabled = false;
    simInput.disabled = false;
    simBtn.disabled = false;

    // Enable trace args if in trace mode
    const traceArgs = document.getElementById('trace-args');
    if (traceArgs) traceArgs.disabled = false;

    // Sync mode toggle state
    onSimModeChange();

    // Set default input
    simInput.value = '{"query": "Hello, agent!"}';
}

/**
 * Disable simulation controls (on analysis failure)
 */
function disableSimControls() {
    document.getElementById('entry-select').disabled = true;
    document.getElementById('sim-input').disabled = true;
    document.getElementById('sim-btn').disabled = true;
    document.getElementById('sim-step-btn').disabled = true;
    document.getElementById('sim-reset-btn').disabled = true;
    const traceArgs = document.getElementById('trace-args');
    if (traceArgs) traceArgs.disabled = true;
}

/**
 * Set status bar text
 */
function setStatus(text, level) {
    const statusEl = document.getElementById('status-text');
    statusEl.textContent = text;

    // Color based on level
    const colors = {
        info: '#7aa2f7',
        success: '#9ece6a',
        warn: '#ff9e64',
        error: '#f7768e',
    };
    statusEl.style.color = colors[level] || '#a9b1d6';
}

/**
 * Shorten a file path for display
 */
function _shortenPath(path) {
    if (!path) return '';
    if (path.length <= 35) return path;
    const parts = path.replace(/\\/g, '/').split('/');
    if (parts.length <= 3) return path;
    return parts[0] + '/.../' + parts.slice(-2).join('/');
}

/**
 * Shorten a node ID for display in dropdowns
 * e.g. "project_original.milvus_build.csv_api.upload_csv" → "csv_api.upload_csv"
 */
function _shortNodeId(nodeId) {
    const parts = nodeId.split('.');
    if (parts.length <= 2) return nodeId;
    // Keep last 2 segments (e.g., "Class.method" or "module.function")
    return parts.slice(-2).join('.');
}

// === Keyboard shortcuts ===
document.addEventListener('keydown', function (e) {
    const active = document.activeElement;
    const isInput = active.tagName === 'INPUT' || active.tagName === 'TEXTAREA' || active.tagName === 'SELECT';

    // Enter to analyze (in path input)
    if (e.key === 'Enter' && active.id === 'project-path') {
        analyzeProject();
        return;
    }
    // Ctrl+F or / to focus search
    if ((e.key === '/' || (e.ctrlKey && e.key === 'f')) && !isInput) {
        e.preventDefault();
        document.getElementById('node-search').focus();
        return;
    }
    // Space to toggle simulation
    if (e.key === ' ' && !isInput) {
        e.preventDefault();
        if (simulationState.running) {
            toggleSimulation();
        }
    }
    // Escape to close sidebar or clear search
    if (e.key === 'Escape') {
        if (active.id === 'node-search') {
            active.value = '';
            onSearchInput('');
            active.blur();
        } else {
            closeSidebar();
        }
    }
    // F to fit graph
    if (e.key === 'f' && !e.ctrlKey && !isInput) {
        fitGraph();
    }
    // 1/2/3 to focus N-hop neighborhood of selected node
    if (!isInput && (e.key === '1' || e.key === '2' || e.key === '3')) {
        const selectedNode = cy && cy.nodes('.highlighted');
        if (selectedNode && selectedNode.length > 0) {
            focusNeighborhood(selectedNode.first().data('id'), parseInt(e.key));
        }
    }
    // 0 to show all nodes
    if (e.key === '0' && !isInput) {
        if (cy) {
            clearHighlight();
            cy.elements().removeClass('dimmed');
        }
    }
});

// Initialize on load
document.addEventListener('DOMContentLoaded', function () {
    initGraph();
    setStatus('就绪 - 输入项目路径开始分析', 'info');

    // Minimap click-to-navigate
    const minimapCanvas = document.getElementById('minimap-canvas');
    if (minimapCanvas) {
        minimapCanvas.addEventListener('click', function (e) {
            if (!cy || cy.nodes().length === 0) return;
            const rect = minimapCanvas.parentElement.getBoundingClientRect();
            const clickX = e.clientX - rect.left;
            const clickY = e.clientY - rect.top;
            const w = rect.width;
            const h = rect.height;

            const bb = cy.elements().boundingBox();
            if (bb.w === 0 || bb.h === 0) return;
            const scale = Math.min((w - 8) / bb.w, (h - 8) / bb.h);
            const offX = (w - bb.w * scale) / 2 - bb.x1 * scale;
            const offY = (h - bb.h * scale) / 2 - bb.y1 * scale;

            const graphX = (clickX - offX) / scale;
            const graphY = (clickY - offY) / scale;
            cy.viewport({
                pan: {
                    x: -graphX * cy.zoom() + cy.width() / 2,
                    y: -graphY * cy.zoom() + cy.height() / 2,
                },
            });
            _renderMinimap();
        });
    }

    // Speed slider label update
    const speedSlider = document.getElementById('sim-speed');
    const speedLabel = document.querySelector('.speed-label');
    if (speedSlider && speedLabel) {
        const updateSpeedLabel = () => {
            const val = parseInt(speedSlider.value);
            speedLabel.textContent = val >= 1000 ? (val / 1000).toFixed(1) + 's' : val + 'ms';
        };
        speedSlider.addEventListener('input', updateSpeedLabel);
        updateSpeedLabel();
    }
});

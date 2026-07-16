/**
 * Graph rendering and interaction using Cytoscape.js
 */

// Node type to color mapping
const NODE_COLORS = {
    entry_point:     '#4CAF50',
    llm_call:        '#2196F3',
    tool:            '#FF9800',
    decision:        '#f44336',
    sub_agent:       '#9C27B0',
    data_transform:  '#607D8B',
    output:          '#FF5722',
    process:         '#9E9E9E',
};

// Node type to shape mapping
const NODE_SHAPES = {
    entry_point:     'round-rectangle',
    llm_call:        'hexagon',
    tool:            'rectangle',
    decision:        'diamond',
    sub_agent:       'octagon',
    data_transform:  'round-rectangle',
    output:          'round-rectangle',
    process:         'ellipse',
};

// Node type display names
const NODE_TYPE_LABELS = {
    entry_point:     '入口点',
    llm_call:        'LLM 调用',
    tool:            '工具',
    decision:        '决策分支',
    sub_agent:       '子 Agent',
    data_transform:  '数据处理',
    output:          '输出',
    process:         '处理',
};

let cy = null;
let currentGraphData = null;
let _moduleCollapsed = false; // track collapse state

/**
 * Initialize the Cytoscape instance
 */
function initGraph() {
    cy = cytoscape({
        container: document.getElementById('cy'),
        style: getCytoscapeStyle(),
        // Interaction options
        minZoom: 0.1,
        maxZoom: 5,
        wheelSensitivity: 0.3,
        boxSelectionEnabled: false,
    });

    // Node click handler
    cy.on('tap', 'node', function (evt) {
        const node = evt.target;
        if (node.data('isGroup')) return; // Skip compound parent nodes
        showNodeDetail(node.data());
        highlightConnected(node);
    });

    // Background click handler
    cy.on('tap', function (evt) {
        if (evt.target === cy) {
            clearHighlight();
        }
    });

    // Hover effects
    cy.on('mouseover', 'node', function (evt) {
        const node = evt.target;
        node.addClass('hover');
        document.getElementById('cy').style.cursor = 'pointer';
    });

    cy.on('mouseout', 'node', function (evt) {
        evt.target.removeClass('hover');
        document.getElementById('cy').style.cursor = 'default';
    });

    // Edge hover
    cy.on('mouseover', 'edge', function (evt) {
        evt.target.addClass('hover');
    });

    cy.on('mouseout', 'edge', function (evt) {
        evt.target.removeClass('hover');
    });

    return cy;
}

/**
 * Get Cytoscape stylesheet
 */
function getCytoscapeStyle() {
    const styles = [
        // Default node style
        {
            selector: 'node',
            style: {
                'label': 'data(label)',
                'text-valign': 'center',
                'text-halign': 'center',
                'font-size': '12px',
                'font-family': '"Segoe UI", "Microsoft YaHei", sans-serif',
                'color': '#fff',
                'text-wrap': 'wrap',
                'text-max-width': '140px',
                'width': 'label',
                'height': 'label',
                'padding': '12px',
                'min-width': '80px',
                'min-height': '36px',
                'border-width': 2,
                'border-color': '#555',
                'text-outline-width': 0,
                'transition-property': 'background-color, border-color, border-width, opacity',
                'transition-duration': '0.3s',
            }
        },
        // Default edge style
        {
            selector: 'edge',
            style: {
                'width': 2,
                'line-color': '#555',
                'target-arrow-color': '#555',
                'target-arrow-shape': 'triangle',
                'curve-style': 'bezier',
                'arrow-scale': 1.2,
                'opacity': 0.7,
                'transition-property': 'line-color, target-arrow-color, width, opacity',
                'transition-duration': '0.3s',
            }
        },
        // Edge labels
        {
            selector: 'edge[label]',
            style: {
                'label': 'data(label)',
                'font-size': '9px',
                'color': '#a9b1d6',
                'text-rotation': 'autorotate',
                'text-background-color': '#1a1b26',
                'text-background-opacity': 0.8,
                'text-background-padding': '3px',
            }
        },
        // Conditional edges - dashed
        {
            selector: 'edge[edgeType = "conditional"]',
            style: {
                'line-style': 'dashed',
                'line-dash-pattern': [6, 3],
            }
        },
        // Hover state
        {
            selector: 'node.hover',
            style: {
                'border-width': 3,
                'border-color': '#7aa2f7',
                'z-index': 10,
            }
        },
        {
            selector: 'edge.hover',
            style: {
                'width': 3,
                'opacity': 1,
                'z-index': 10,
            }
        },
        // Highlighted state (when a node is selected)
        {
            selector: 'node.highlighted',
            style: {
                'border-width': 3,
                'border-color': '#FFD700',
                'z-index': 10,
            }
        },
        {
            selector: 'edge.highlighted',
            style: {
                'width': 3,
                'line-color': '#FFD700',
                'target-arrow-color': '#FFD700',
                'opacity': 1,
                'z-index': 10,
            }
        },
        // Dimmed state
        {
            selector: 'node.dimmed',
            style: {
                'opacity': 0.2,
            }
        },
        {
            selector: 'edge.dimmed',
            style: {
                'opacity': 0.1,
            }
        },
        // Simulation active node
        {
            selector: 'node.sim-active',
            style: {
                'border-width': 4,
                'border-color': '#FFD700',
                'background-opacity': 1,
                'z-index': 100,
            }
        },
        // Simulation visited node
        {
            selector: 'node.sim-visited',
            style: {
                'border-width': 3,
                'border-color': '#9ece6a',
                'opacity': 0.9,
            }
        },
        // Simulation active edge
        {
            selector: 'edge.sim-active',
            style: {
                'width': 4,
                'line-color': '#FFD700',
                'target-arrow-color': '#FFD700',
                'opacity': 1,
                'z-index': 100,
            }
        },
        // Simulation visited edge
        {
            selector: 'edge.sim-visited',
            style: {
                'width': 3,
                'line-color': '#9ece6a',
                'target-arrow-color': '#9ece6a',
                'opacity': 0.9,
            }
        },
        // Hidden nodes
        {
            selector: 'node.hidden',
            style: {
                'display': 'none',
            }
        },
        {
            selector: 'edge.hidden',
            style: {
                'display': 'none',
            }
        },
        // Search match visual
        {
            selector: 'node.search-match',
            style: {
                'border-width': 2,
                'border-color': '#ff9e64',
                'z-index': 50,
            }
        },
        // Current search result
        {
            selector: 'node.search-current',
            style: {
                'border-width': 4,
                'border-color': '#ff9e64',
                'z-index': 60,
            }
        },
        // Compound parent (module group) nodes
        {
            selector: ':parent',
            style: {
                'background-color': '#1e2030',
                'background-opacity': 0.7,
                'border-width': 1,
                'border-color': '#3b4261',
                'border-opacity': 0.6,
                'shape': 'round-rectangle',
                'padding': '16px',
                'text-valign': 'top',
                'text-halign': 'center',
                'label': 'data(label)',
                'font-size': '10px',
                'color': '#565f89',
                'font-weight': '600',
                'text-margin-y': -4,
                'compound-sizing-wrt-labels': 'include',
            }
        },
    ];

    // Add node type specific styles
    for (const [type, color] of Object.entries(NODE_COLORS)) {
        styles.push({
            selector: `node[nodeType = "${type}"]`,
            style: {
                'background-color': color,
                'shape': NODE_SHAPES[type] || 'ellipse',
                'border-color': _darken(color, 30),
            }
        });
    }

    return styles;
}

/**
 * Render graph data to Cytoscape
 */
let _compoundGroupingEnabled = false;

function renderGraph(graphData) {
    if (!cy) {
        initGraph();
    }

    currentGraphData = graphData;
    _moduleCollapsed = false;
    cy.elements().remove();

    // Collect unique modules for compound grouping
    const modules = new Set();
    const moduleNodeCounts = {};
    for (const node of graphData.nodes) {
        if (node.module_id) {
            modules.add(node.module_id);
            moduleNodeCounts[node.module_id] = (moduleNodeCounts[node.module_id] || 0) + 1;
        }
    }

    // For large graphs, start flat (no compound grouping) for better layout
    const nodeCount = graphData.nodes.length;
    const useCompound = nodeCount <= 60;
    _compoundGroupingEnabled = useCompound;

    const elements = [];

    if (useCompound) {
        // Add compound parent nodes (file-level groups)
        for (const moduleId of modules) {
            const parts = moduleId.split('/');
            const shortLabel = parts.length > 1 ? parts.slice(-2).join('/') : parts[0];
            elements.push({
                group: 'nodes',
                data: {
                    id: 'group:' + moduleId,
                    label: '📁 ' + shortLabel,
                    nodeType: 'module_group',
                    isGroup: true,
                }
            });
        }
    }

    // Add function nodes
    for (const node of graphData.nodes) {
        const data = {
            id: node.id,
            label: _formatLabel(node.label, node.type),
            nodeType: node.type,
            ...node,
        };
        if (useCompound && node.module_id) {
            data.parent = 'group:' + node.module_id;
        }
        elements.push({
            group: 'nodes',
            data: data,
        });
    }

    // Add edges
    for (const edge of graphData.edges) {
        elements.push({
            group: 'edges',
            data: {
                id: edge.id,
                source: edge.source,
                target: edge.target,
                edgeType: edge.type,
                label: edge.label || '',
                condition: edge.condition || '',
            }
        });
    }

    cy.add(elements);

    // Populate module filter panel
    _populateModuleFilter(modules, moduleNodeCounts);

    // Apply layout
    if (nodeCount > 80) {
        applyLayout('cose');
    } else {
        applyLayout('dagre');
    }

    // Sync layout dropdown
    const layoutSelect = document.getElementById('layout-select');
    if (layoutSelect) {
        layoutSelect.value = nodeCount > 80 ? 'cose' : 'dagre';
    }

    // Ensure readable zoom — don't zoom out too far
    _ensureReadableZoom();

    // Enable controls
    document.getElementById('layout-btn').disabled = false;
    document.getElementById('fit-btn').disabled = false;
    document.getElementById('export-btn').disabled = false;
    document.getElementById('layout-select').disabled = false;

    // Update UI hints
    const groupBtn = document.getElementById('collapse-btn');
    if (groupBtn) {
        groupBtn.textContent = useCompound ? '折叠模块' : '按模块分组';
    }

    // Update stats overlay
    _updateGraphStats(graphData, modules.size);

    // Start minimap rendering
    _startMinimap();
}

/**
 * Ensure zoom is not too small to read labels
 */
function _ensureReadableZoom() {
    if (!cy) return;
    const minReadable = 0.45;
    if (cy.zoom() < minReadable) {
        // Center on the densest region instead of fitting everything
        cy.zoom({ level: minReadable, position: _findGraphCenter() });
    }
}

function _findGraphCenter() {
    // Find centroid of all non-group nodes
    let sx = 0, sy = 0, n = 0;
    cy.nodes().forEach(node => {
        if (!node.data('isGroup')) {
            sx += node.position('x');
            sy += node.position('y');
            n++;
        }
    });
    return n > 0 ? { x: sx / n, y: sy / n } : { x: 0, y: 0 };
}

/**
 * Apply a layout to the graph
 */
function applyLayout(name) {
    if (!cy || cy.nodes().length === 0) return;

    const layouts = {
        dagre: {
            name: 'dagre',
            rankDir: 'TB',
            nodeSep: 40,
            rankSep: 60,
            edgeSep: 15,
            animate: cy.nodes().length < 300,
            animationDuration: 500,
            fit: true,
            padding: 20,
        },
        breadthfirst: {
            name: 'breadthfirst',
            directed: true,
            spacingFactor: 1.2,
            animate: cy.nodes().length < 300,
            animationDuration: 500,
            fit: true,
        },
        circle: {
            name: 'circle',
            animate: cy.nodes().length < 500,
            animationDuration: 500,
            fit: true,
        },
        concentric: {
            name: 'concentric',
            concentric: function (node) {
                const type = node.data('nodeType');
                const order = { entry_point: 5, llm_call: 4, decision: 3, tool: 2, sub_agent: 2, output: 1, process: 0 };
                return order[type] || 0;
            },
            levelWidth: () => 3,
            minNodeSpacing: 30,
            animate: cy.nodes().length < 300,
            animationDuration: 500,
            fit: true,
        },
        cose: {
            name: 'cose',
            nodeOverlap: 20,
            idealEdgeLength: function(edge) { return _compoundGroupingEnabled ? 60 : 50; },
            nodeRepulsion: function(node) { return _compoundGroupingEnabled ? 4500 : 3000; },
            gravity: _compoundGroupingEnabled ? 1.2 : 2.5,
            gravityCompound: 1.5,
            gravityRange: 3.8,
            gravityRangeCompound: 2.0,
            nestingFactor: 1.2,
            componentSpacing: _compoundGroupingEnabled ? 60 : 40,
            numIter: cy.nodes().length > 500 ? 500 : 1500,
            animate: false,
            fit: true,
            padding: 30,
        },
    };

    const layoutConfig = layouts[name] || layouts.dagre;
    cy.layout(layoutConfig).run();
}

/**
 * Show node detail in the right sidebar
 */
function showNodeDetail(nodeData) {
    const sidebar = document.getElementById('sidebar-right');
    sidebar.classList.remove('collapsed');

    const detail = document.getElementById('node-detail');
    const color = NODE_COLORS[nodeData.nodeType] || '#9E9E9E';
    const typeLabel = NODE_TYPE_LABELS[nodeData.nodeType] || nodeData.nodeType;

    let html = `
        <div class="detail-section">
            <span class="detail-badge" style="background:${color}">${typeLabel}</span>
            ${nodeData.is_async ? '<span class="detail-badge" style="background:#565f89">async</span>' : ''}
        </div>

        <div class="detail-section">
            <h4>基本信息</h4>
            <div class="detail-info">
                <div class="detail-row">
                    <span class="detail-label">名称</span>
                    <span class="detail-value"><strong>${_escapeHtml(nodeData.id)}</strong></span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">文件</span>
                    <span class="detail-value">${_escapeHtml(nodeData.filepath)}:${nodeData.lineno}</span>
                </div>
                ${nodeData.class_name ? `
                <div class="detail-row">
                    <span class="detail-label">所属类</span>
                    <span class="detail-value">${_escapeHtml(nodeData.class_name)}</span>
                </div>` : ''}
                <div class="detail-row">
                    <span class="detail-label">置信度</span>
                    <span class="detail-value">${(nodeData.confidence * 100).toFixed(0)}%</span>
                </div>
                <div class="detail-row">
                    <span class="detail-label">原因</span>
                    <span class="detail-value">${_escapeHtml(nodeData.reason)}</span>
                </div>
            </div>
        </div>

        <div class="detail-section">
            <h4>邻域聚焦</h4>
            <div class="neighborhood-btns">
                <button class="btn-sm" onclick="focusNeighborhood('${_escapeHtml(nodeData.id)}', 1)">1 跳</button>
                <button class="btn-sm" onclick="focusNeighborhood('${_escapeHtml(nodeData.id)}', 2)">2 跳</button>
                <button class="btn-sm" onclick="focusNeighborhood('${_escapeHtml(nodeData.id)}', 3)">3 跳</button>
                <button class="btn-sm" onclick="clearHighlight(); cy.elements().removeClass('dimmed')">显示全部</button>
            </div>
        </div>
    `;

    // Parameters
    if (nodeData.parameters && nodeData.parameters.length > 0) {
        html += `
            <div class="detail-section">
                <h4>参数</h4>
                <div class="detail-tags">
                    ${nodeData.parameters.map(p => `<span class="detail-tag">${_escapeHtml(p)}</span>`).join('')}
                </div>
            </div>
        `;
    }

    // Call relationships — who calls this, what this calls
    if (cy) {
        const nodeEle = cy.getElementById(nodeData.id);
        if (nodeEle.length > 0) {
            const incomers = nodeEle.incomers('node').filter(n => !n.data('isGroup'));
            const outgoers = nodeEle.outgoers('node').filter(n => !n.data('isGroup'));

            if (incomers.length > 0) {
                html += `
                    <div class="detail-section">
                        <h4>被调用 (${incomers.length})</h4>
                        <div class="detail-tags">
                            ${incomers.map(n => {
                                const nid = n.data('id');
                                const short = nid.split('.').slice(-2).join('.');
                                const color = NODE_COLORS[n.data('nodeType')] || '#9E9E9E';
                                return `<span class="detail-tag clickable" style="border-left:3px solid ${color}" onclick="focusNode('${_escapeHtml(nid)}')">${_escapeHtml(short)}</span>`;
                            }).join('')}
                        </div>
                    </div>
                `;
            }

            if (outgoers.length > 0) {
                html += `
                    <div class="detail-section">
                        <h4>调用 (${outgoers.length})</h4>
                        <div class="detail-tags">
                            ${outgoers.map(n => {
                                const nid = n.data('id');
                                const short = nid.split('.').slice(-2).join('.');
                                const color = NODE_COLORS[n.data('nodeType')] || '#9E9E9E';
                                return `<span class="detail-tag clickable" style="border-left:3px solid ${color}" onclick="focusNode('${_escapeHtml(nid)}')">${_escapeHtml(short)}</span>`;
                            }).join('')}
                        </div>
                    </div>
                `;
            }
        }
    }

    // Decorators
    if (nodeData.decorators && nodeData.decorators.length > 0) {
        html += `
            <div class="detail-section">
                <h4>装饰器</h4>
                <div class="detail-tags">
                    ${nodeData.decorators.map(d => `<span class="detail-tag">@${_escapeHtml(d)}</span>`).join('')}
                </div>
            </div>
        `;
    }

    // Docstring
    if (nodeData.docstring) {
        html += `
            <div class="detail-section">
                <h4>文档说明</h4>
                <div class="detail-code">${_escapeHtml(nodeData.docstring)}</div>
            </div>
        `;
    }

    // Prompt preview
    if (nodeData.has_prompts && nodeData.prompt_preview) {
        html += `
            <div class="detail-section">
                <h4>Prompt 模板</h4>
                <div class="detail-prompt">${_escapeHtml(nodeData.prompt_preview)}</div>
            </div>
        `;
    }

    // Branches
    if (nodeData.has_branches) {
        html += `
            <div class="detail-section">
                <h4>分支逻辑</h4>
                <div class="detail-info">
                    <div class="detail-row">
                        <span class="detail-label">分支数</span>
                        <span class="detail-value">${nodeData.branch_count} 个分支点</span>
                    </div>
                </div>
            </div>
        `;
    }

    // Source code
    if (nodeData.source_code) {
        html += `
            <div class="detail-section">
                <h4>源代码</h4>
                <div class="detail-code syntax-hl">${_highlightPython(nodeData.source_code)}</div>
            </div>
        `;
    }

    detail.innerHTML = html;
}

/**
 * Highlight a node and its connected elements
 */
function highlightConnected(node) {
    clearHighlight();

    const neighborhood = node.neighborhood().add(node);
    cy.elements().addClass('dimmed');
    neighborhood.removeClass('dimmed');
    node.addClass('highlighted');
    node.connectedEdges().addClass('highlighted');
}

/**
 * Clear all highlights
 */
function clearHighlight() {
    cy.elements().removeClass('dimmed highlighted');
}

/**
 * Toggle visibility of a node type
 */
function toggleNodeType(type) {
    if (!cy) return;

    const nodes = cy.nodes(`[nodeType = "${type}"]`);
    nodes.toggleClass('hidden');

    // Also hide/show connected edges where both endpoints are hidden
    cy.edges().forEach(edge => {
        const src = edge.source();
        const tgt = edge.target();
        if (src.hasClass('hidden') || tgt.hasClass('hidden')) {
            edge.addClass('hidden');
        } else {
            edge.removeClass('hidden');
        }
    });
}

/**
 * Close the right sidebar
 */
function closeSidebar() {
    document.getElementById('sidebar-right').classList.add('collapsed');
    clearHighlight();
}

/**
 * Relayout the graph
 */
function relayout() {
    const layoutName = document.getElementById('layout-select').value;
    applyLayout(layoutName);
}

/**
 * Change layout from dropdown
 */
function changeLayout() {
    relayout();
}

/**
 * Fit the graph to the viewport
 */
function fitGraph() {
    if (cy) {
        cy.fit(undefined, 30);
    }
}

/**
 * Search nodes by name — highlight matches, dim others, support navigation
 */
let _searchTimeout = null;
let _searchResults = [];   // Array of matched node IDs
let _searchIndex = -1;     // Current index in search results

function onSearchInput(query) {
    if (_searchTimeout) clearTimeout(_searchTimeout);
    _searchTimeout = setTimeout(() => _doSearch(query), 150);
}

function _doSearch(query) {
    if (!cy) return;
    const countEl = document.getElementById('search-count');
    _searchResults = [];
    _searchIndex = -1;

    if (!query || query.trim().length === 0) {
        cy.elements().removeClass('dimmed search-match search-current');
        if (countEl) countEl.textContent = '';
        return;
    }

    const q = query.toLowerCase();
    const matchNodes = cy.nodes().filter(n => {
        if (n.data('isGroup')) return false;
        const id = (n.data('id') || '').toLowerCase();
        const label = (n.data('label') || '').toLowerCase();
        return id.includes(q) || label.includes(q);
    });

    if (matchNodes.length > 0) {
        cy.elements().addClass('dimmed');
        cy.elements().removeClass('search-match search-current');
        matchNodes.removeClass('dimmed').addClass('search-match');
        matchNodes.connectedEdges().removeClass('dimmed');
        matchNodes.parents().removeClass('dimmed');
        _searchResults = matchNodes.map(n => n.data('id'));
        if (countEl) countEl.textContent = `${matchNodes.length} 个 ▲▼`;
        // Auto-focus first result
        _searchIndex = 0;
        _highlightSearchCurrent();
    } else {
        cy.elements().removeClass('dimmed search-match search-current');
        if (countEl) countEl.textContent = '无';
    }
}

function searchNext() {
    if (_searchResults.length === 0) return;
    _searchIndex = (_searchIndex + 1) % _searchResults.length;
    _highlightSearchCurrent();
}

function searchPrev() {
    if (_searchResults.length === 0) return;
    _searchIndex = (_searchIndex - 1 + _searchResults.length) % _searchResults.length;
    _highlightSearchCurrent();
}

function _highlightSearchCurrent() {
    if (!cy || _searchResults.length === 0 || _searchIndex < 0) return;
    cy.elements().removeClass('search-current');
    const nodeId = _searchResults[_searchIndex];
    const node = cy.getElementById(nodeId);
    if (node.length > 0) {
        node.addClass('search-current');
        cy.animate({ center: { eles: node }, duration: 250 });
    }
    const countEl = document.getElementById('search-count');
    if (countEl) countEl.textContent = `${_searchIndex + 1}/${_searchResults.length} ▲▼`;
}

/**
 * Focus on a specific node: center, zoom, and highlight it
 */
function focusNode(nodeId) {
    if (!cy) return;
    const node = cy.getElementById(nodeId);
    if (node.length === 0) return;

    clearHighlight();
    cy.animate({
        fit: { eles: node, padding: 120 },
        duration: 400,
    });

    setTimeout(() => {
        showNodeDetail(node.data());
        highlightConnected(node);
    }, 420);
}

/**
 * Show only the N-hop neighborhood of a node (subgraph focus)
 */
function focusNeighborhood(nodeId, hops) {
    if (!cy) return;
    const node = cy.getElementById(nodeId);
    if (node.length === 0) return;

    // BFS to collect N-hop neighborhood
    let frontier = cy.collection().merge(node);
    let visited = cy.collection().merge(node);

    for (let i = 0; i < hops; i++) {
        let nextFrontier = cy.collection();
        frontier.forEach(n => {
            const neighbors = n.neighborhood('node').filter(nn => !nn.data('isGroup'));
            nextFrontier = nextFrontier.merge(neighbors);
        });
        frontier = nextFrontier.difference(visited);
        visited = visited.merge(frontier);
    }

    // Include edges between visited nodes and their parents
    const visitedEdges = visited.edgesWith(visited);
    const parents = visited.parents();

    // Dim everything, then un-dim the neighborhood
    cy.elements().addClass('dimmed').removeClass('search-match search-current');
    visited.removeClass('dimmed');
    visitedEdges.removeClass('dimmed');
    parents.removeClass('dimmed');

    // Highlight the center node
    node.addClass('highlighted');
    node.connectedEdges().filter(e => visited.contains(e.source()) && visited.contains(e.target())).addClass('highlighted');

    // Fit view to the subgraph
    cy.animate({
        fit: { eles: visited.merge(parents), padding: 40 },
        duration: 400,
    });

    setStatus(`聚焦 ${nodeId.split('.').slice(-2).join('.')} 的 ${hops} 跳邻域 (${visited.length} 节点)`, 'info');
}

/**
 * Export the graph as a PNG image
 */
function exportImage() {
    if (!cy) return;
    const png = cy.png({
        output: 'blob',
        bg: '#1a1b26',
        full: true,
        scale: 2,
        maxWidth: 8000,
        maxHeight: 8000,
    });
    const url = URL.createObjectURL(png);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'agent-flow-graph.png';
    a.click();
    URL.revokeObjectURL(url);
    setStatus('图片已导出', 'success');
}

// === Graph stats overlay ===

function _updateGraphStats(graphData, moduleCount) {
    const statsEl = document.getElementById('graph-stats');
    if (!statsEl) return;
    statsEl.style.display = '';
    document.getElementById('stat-nodes').textContent = graphData.nodes.length;
    document.getElementById('stat-edges').textContent = graphData.edges.length;
    document.getElementById('stat-modules').textContent = moduleCount;
}

// === Minimap ===

let _minimapInterval = null;
let _minimapViewportHandler = null;

function _stopMinimap() {
    if (_minimapInterval) {
        clearInterval(_minimapInterval);
        _minimapInterval = null;
    }
    if (_minimapViewportHandler && cy) {
        cy.off('viewport', _minimapViewportHandler);
        _minimapViewportHandler = null;
    }
}

function _startMinimap() {
    _stopMinimap();
    _renderMinimap();
    _minimapInterval = setInterval(_renderMinimap, 1500);

    // Debounced viewport handler (stable reference for removal)
    _minimapViewportHandler = _debounce(_renderMinimap, 250);
    if (cy) {
        cy.on('viewport', _minimapViewportHandler);
    }
}

function _renderMinimap() {
    if (!cy || cy.nodes().length === 0) return;
    const canvas = document.getElementById('minimap-canvas');
    if (!canvas) return;
    const ctx = canvas.getContext('2d');

    const rect = canvas.parentElement.getBoundingClientRect();
    canvas.width = rect.width * 2; // retina
    canvas.height = rect.height * 2;
    ctx.scale(2, 2);

    const w = rect.width;
    const h = rect.height;

    // Clear
    ctx.fillStyle = '#1a1b26';
    ctx.fillRect(0, 0, w, h);

    // Get graph bounding box
    const bb = cy.elements().boundingBox();
    if (bb.w === 0 || bb.h === 0) return;

    const scale = Math.min((w - 8) / bb.w, (h - 8) / bb.h);
    const offX = (w - bb.w * scale) / 2 - bb.x1 * scale;
    const offY = (h - bb.h * scale) / 2 - bb.y1 * scale;

    // Draw edges
    ctx.strokeStyle = '#3b4261';
    ctx.lineWidth = 0.5;
    cy.edges(':visible').forEach(edge => {
        const sp = edge.sourceEndpoint();
        const tp = edge.targetEndpoint();
        ctx.beginPath();
        ctx.moveTo(sp.x * scale + offX, sp.y * scale + offY);
        ctx.lineTo(tp.x * scale + offX, tp.y * scale + offY);
        ctx.stroke();
    });

    // Draw nodes
    cy.nodes(':visible').forEach(node => {
        if (node.data('isGroup')) return;
        const pos = node.position();
        const color = NODE_COLORS[node.data('nodeType')] || '#9E9E9E';
        ctx.fillStyle = color;
        ctx.fillRect(pos.x * scale + offX - 1.5, pos.y * scale + offY - 1.5, 3, 3);
    });

    // Draw viewport rectangle
    const ext = cy.extent();
    ctx.strokeStyle = '#7aa2f7';
    ctx.lineWidth = 1;
    ctx.strokeRect(
        ext.x1 * scale + offX,
        ext.y1 * scale + offY,
        ext.w * scale,
        ext.h * scale
    );
}

function _debounce(fn, ms) {
    let timer;
    return function () {
        clearTimeout(timer);
        timer = setTimeout(fn, ms);
    };
}

// === Module filter functions ===

/**
 * Populate the module filter panel with checkboxes
 */
function _populateModuleFilter(modules, moduleNodeCounts) {
    const panel = document.getElementById('module-filter-panel');
    const list = document.getElementById('module-filter-list');

    if (modules.size === 0) {
        panel.style.display = 'none';
        return;
    }
    panel.style.display = '';

    // Sort modules by node count descending
    const sorted = [...modules].sort((a, b) =>
        (moduleNodeCounts[b] || 0) - (moduleNodeCounts[a] || 0)
    );

    list.innerHTML = sorted.map(mod => {
        const parts = mod.split('/');
        const shortLabel = parts.length > 1 ? parts.slice(-2).join('/') : parts[0];
        const cnt = moduleNodeCounts[mod] || 0;
        return `<label class="module-filter-item" title="${_escapeHtml(mod)}">
            <input type="checkbox" checked onchange="toggleModule('${_escapeHtml(mod)}', this.checked)">
            <span class="module-name">${_escapeHtml(shortLabel)}</span>
            <span class="module-count">${cnt}</span>
        </label>`;
    }).join('');
}

/**
 * Toggle visibility of a module group and its children
 */
function toggleModule(moduleId, visible) {
    if (!cy) return;
    const groupId = 'group:' + moduleId;
    const group = cy.getElementById(groupId);
    if (group.length === 0) return;

    const children = group.children();
    if (visible) {
        group.removeClass('hidden');
        children.removeClass('hidden');
    } else {
        group.addClass('hidden');
        children.addClass('hidden');
    }
    // Update edge visibility
    cy.edges().forEach(edge => {
        const src = edge.source();
        const tgt = edge.target();
        if (src.hasClass('hidden') || tgt.hasClass('hidden')) {
            edge.addClass('hidden');
        } else {
            edge.removeClass('hidden');
        }
    });
}

/**
 * Toggle all modules on or off
 */
function toggleAllModules(show) {
    const checkboxes = document.querySelectorAll('#module-filter-list input[type="checkbox"]');
    checkboxes.forEach(cb => {
        cb.checked = show;
    });
    if (!cy) return;
    if (show) {
        cy.elements().removeClass('hidden');
    } else {
        cy.nodes().addClass('hidden');
        cy.edges().addClass('hidden');
    }
}

/**
 * Collapse all module groups into single representative nodes,
 * or expand them back to individual nodes
 */
function collapseAllModules() {
    if (!cy || !currentGraphData) return;

    if (_moduleCollapsed) {
        // Expand: re-render the full graph
        _moduleCollapsed = false;
        document.getElementById('collapse-btn').textContent = _compoundGroupingEnabled ? '折叠模块' : '按模块分组';
        renderGraph(currentGraphData);
        return;
    }

    // If compound grouping is off, enable it first (adds parent groups)
    if (!_compoundGroupingEnabled) {
        _compoundGroupingEnabled = true;
        // Re-render with compound groups, then the user sees grouped layout
        cy.elements().remove();
        const modules = new Set();
        const elements = [];
        for (const node of currentGraphData.nodes) {
            if (node.module_id) modules.add(node.module_id);
        }
        for (const moduleId of modules) {
            const parts = moduleId.split('/');
            const shortLabel = parts.length > 1 ? parts.slice(-2).join('/') : parts[0];
            elements.push({ group: 'nodes', data: { id: 'group:' + moduleId, label: '📁 ' + shortLabel, nodeType: 'module_group', isGroup: true } });
        }
        for (const node of currentGraphData.nodes) {
            const data = { id: node.id, label: _formatLabel(node.label, node.type), nodeType: node.type, ...node };
            if (node.module_id) data.parent = 'group:' + node.module_id;
            elements.push({ group: 'nodes', data });
        }
        for (const edge of currentGraphData.edges) {
            elements.push({ group: 'edges', data: { id: edge.id, source: edge.source, target: edge.target, edgeType: edge.type, label: edge.label || '', condition: edge.condition || '' } });
        }
        cy.add(elements);
        applyLayout('cose');
        _ensureReadableZoom();
        document.getElementById('collapse-btn').textContent = '折叠模块';
        setStatus('已启用模块分组视图', 'info');
        return;
    }

    _moduleCollapsed = true;
    document.getElementById('collapse-btn').textContent = '展开模块';

    // Collect modules
    const modules = {};
    for (const node of currentGraphData.nodes) {
        const mod = node.module_id || '__root__';
        if (!modules[mod]) modules[mod] = { nodes: [], types: {} };
        modules[mod].nodes.push(node);
        modules[mod].types[node.type] = (modules[mod].types[node.type] || 0) + 1;
    }

    // Build collapsed graph
    cy.elements().remove();
    const elements = [];

    // Add one node per module
    for (const [mod, info] of Object.entries(modules)) {
        const parts = mod.split('/');
        const shortLabel = parts.length > 1 ? parts.slice(-2).join('/') : parts[0];
        // Determine dominant type for coloring
        let dominantType = 'process';
        let maxCount = 0;
        for (const [type, count] of Object.entries(info.types)) {
            if (count > maxCount) { maxCount = count; dominantType = type; }
        }
        elements.push({
            group: 'nodes',
            data: {
                id: 'mod:' + mod,
                label: `📁 ${shortLabel}\n(${info.nodes.length} 节点)`,
                nodeType: dominantType,
                isCollapsed: true,
                moduleId: mod,
                nodeCount: info.nodes.length,
            }
        });
    }

    // Add edges between collapsed modules
    const modEdgeSet = new Set();
    for (const edge of currentGraphData.edges) {
        const srcNode = currentGraphData.nodes.find(n => n.id === edge.source);
        const tgtNode = currentGraphData.nodes.find(n => n.id === edge.target);
        if (!srcNode || !tgtNode) continue;
        const srcMod = 'mod:' + (srcNode.module_id || '__root__');
        const tgtMod = 'mod:' + (tgtNode.module_id || '__root__');
        if (srcMod === tgtMod) continue; // skip intra-module edges
        const key = srcMod + '|' + tgtMod;
        if (modEdgeSet.has(key)) continue;
        modEdgeSet.add(key);
        elements.push({
            group: 'edges',
            data: {
                id: 'me_' + modEdgeSet.size,
                source: srcMod,
                target: tgtMod,
                edgeType: 'call',
                label: '',
            }
        });
    }

    cy.add(elements);

    // Handle click on collapsed module to expand it
    cy.off('tap', 'node');
    cy.on('tap', 'node', function (evt) {
        const node = evt.target;
        if (node.data('isCollapsed')) {
            // Expand just this module
            _expandModule(node.data('moduleId'));
        } else if (!node.data('isGroup')) {
            showNodeDetail(node.data());
            highlightConnected(node);
        }
    });

    applyLayout('cose');
    setStatus(`已折叠为 ${Object.keys(modules).length} 个模块节点`, 'info');
}

/**
 * Expand a single module from collapsed view — re-render the full graph
 * and focus on that module
 */
function _expandModule(moduleId) {
    _moduleCollapsed = false;
    document.getElementById('collapse-btn').textContent = '折叠模块';
    renderGraph(currentGraphData);

    // After re-render, hide all modules except the selected one
    const checkboxes = document.querySelectorAll('#module-filter-list input[type="checkbox"]');
    checkboxes.forEach(cb => {
        const modId = cb.getAttribute('onchange').match(/toggleModule\('([^']+)'/)?.[1];
        if (modId && modId !== moduleId) {
            cb.checked = false;
            toggleModule(modId, false);
        }
    });

    // Focus on the module group
    setTimeout(() => {
        const groupNode = cy.getElementById('group:' + moduleId);
        if (groupNode.length > 0) {
            cy.animate({ fit: { eles: groupNode.add(groupNode.children()), padding: 40 }, duration: 400 });
        }
    }, 600);
}

// === Source code highlighting ===

/**
 * Simple Python syntax highlighter for the detail panel.
 * Uses a tokenizer approach to avoid regex conflicts with HTML entities.
 */
function _highlightPython(code) {
    if (!code) return '';

    // Tokenize first, then render — avoids regex-on-HTML conflicts
    const tokens = [];
    const lines = code.split('\n');

    for (const line of lines) {
        let i = 0;
        while (i < line.length) {
            // Triple-quoted strings
            if (line.substring(i, i + 3) === '"""' || line.substring(i, i + 3) === "'''") {
                const q = line.substring(i, i + 3);
                let end = line.indexOf(q, i + 3);
                if (end === -1) end = line.length - 3;
                tokens.push({ type: 'str', text: line.substring(i, end + 3) });
                i = end + 3;
                continue;
            }
            // Single/double strings
            if (line[i] === '"' || line[i] === "'") {
                const q = line[i];
                let j = i + 1;
                while (j < line.length && line[j] !== q) {
                    if (line[j] === '\\') j++;
                    j++;
                }
                tokens.push({ type: 'str', text: line.substring(i, j + 1) });
                i = j + 1;
                continue;
            }
            // Comments
            if (line[i] === '#') {
                tokens.push({ type: 'cmt', text: line.substring(i) });
                i = line.length;
                continue;
            }
            // Decorator
            if (line[i] === '@' && (i === 0 || /\s/.test(line[i - 1]))) {
                const m = line.substring(i).match(/^@\w+/);
                if (m) {
                    tokens.push({ type: 'dec', text: m[0] });
                    i += m[0].length;
                    continue;
                }
            }
            // Word (keyword, identifier, number)
            const wm = line.substring(i).match(/^[a-zA-Z_]\w*/);
            if (wm) {
                const kws = new Set(['def','class','if','elif','else','for','while','try','except','finally','with','as','return','yield','import','from','raise','pass','break','continue','and','or','not','in','is','None','True','False','self','async','await','lambda']);
                const word = wm[0];
                if (kws.has(word)) {
                    tokens.push({ type: 'kw', text: word });
                } else if ((i >= 4 && line.substring(i - 4, i).match(/(def |class )/)) || (i >= 6 && line.substring(i - 6, i).match(/(class )/))) {
                    tokens.push({ type: 'fn', text: word });
                } else {
                    tokens.push({ type: 'plain', text: word });
                }
                i += word.length;
                continue;
            }
            const nm = line.substring(i).match(/^\d+\.?\d*/);
            if (nm) {
                tokens.push({ type: 'num', text: nm[0] });
                i += nm[0].length;
                continue;
            }
            // Other character
            tokens.push({ type: 'plain', text: line[i] });
            i++;
        }
        tokens.push({ type: 'plain', text: '\n' });
    }

    const classMap = { str: 'py-str', cmt: 'py-cmt', kw: 'py-kw', dec: 'py-dec', num: 'py-num', fn: 'py-fn' };
    return tokens.map(t => {
        const escaped = _escapeHtml(t.text);
        const cls = classMap[t.type];
        return cls ? `<span class="${cls}">${escaped}</span>` : escaped;
    }).join('');
}

// === Helper functions ===

function _formatLabel(name, type) {
    // Add prefix icon based on type
    const icons = {
        entry_point: '▶ ',
        llm_call: '🤖 ',
        tool: '🔧 ',
        decision: '◆ ',
        sub_agent: '🔄 ',
        output: '📤 ',
        data_transform: '⚙ ',
    };

    // Shorten: "Class.method" is fine, but "module.sub.Class.method" → "Class.method"
    // Just keep the last 2 dot-segments at most
    const parts = name.split('.');
    let shortName;
    if (parts.length > 2) {
        shortName = parts.slice(-2).join('.');
    } else {
        shortName = name;
    }
    // Truncate if still long
    if (shortName.length > 25) {
        shortName = shortName.slice(0, 22) + '...';
    }

    return (icons[type] || '') + shortName;
}

function _escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function _darken(hex, percent) {
    const num = parseInt(hex.replace('#', ''), 16);
    const amt = Math.round(2.55 * percent);
    const R = Math.max(0, (num >> 16) - amt);
    const G = Math.max(0, ((num >> 8) & 0x00FF) - amt);
    const B = Math.max(0, (num & 0x0000FF) - amt);
    return '#' + (0x1000000 + R * 0x10000 + G * 0x100 + B).toString(16).slice(1);
}

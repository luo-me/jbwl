let graphData = { nodes: [], edges: [] };
let selectedAgent = null;
let ws = null;
let simulation = null;
let svgSelection = null;
let linkSelection = null;
let nodeSelection = null;
let labelSelection = null;

async function init() {
    await loadGraph();
    initForceGraph();
    initWebSocket();
    loadStats();
    loadAgentList();
}

async function loadGraph() {
    const resp = await fetch('/api/network/graph');
    graphData = await resp.json();
}

function initForceGraph() {
    const container = document.getElementById('forceGraph');
    const width = container.clientWidth;
    const height = container.clientHeight;

    svgSelection = d3.select('#forceGraph');
    svgSelection.selectAll('*').remove();

    svgSelection.append('defs').append('marker')
        .attr('id', 'arrowhead')
        .attr('viewBox', '0 -5 10 10')
        .attr('refX', 22)
        .attr('refY', 0)
        .attr('markerWidth', 6)
        .attr('markerHeight', 6)
        .attr('orient', 'auto')
        .append('path')
        .attr('d', 'M0,-5L10,0L0,5')
        .attr('fill', '#95a5a6');

    const g = svgSelection.append('g');

    svgSelection.call(d3.zoom()
        .scaleExtent([0.3, 5])
        .on('zoom', (event) => {
            g.attr('transform', event.transform);
        }));

    linkSelection = g.append('g')
        .attr('class', 'links')
        .selectAll('line');

    nodeSelection = g.append('g')
        .attr('class', 'nodes')
        .selectAll('circle');

    labelSelection = g.append('g')
        .attr('class', 'labels')
        .selectAll('text');

    updateGraph();
}

function updateGraph() {
    if (!svgSelection) return;

    const container = document.getElementById('forceGraph');
    const width = container.clientWidth;
    const height = container.clientHeight;

    const nodes = graphData.nodes.map(n => ({ ...n }));
    const edges = graphData.edges.map(e => ({
        ...e,
        source: e.source,
        target: e.target
    }));

    if (simulation) simulation.stop();

    simulation = d3.forceSimulation(nodes)
        .force('link', d3.forceLink(edges).id(d => d.id).distance(120))
        .force('charge', d3.forceManyBody().strength(-300))
        .force('center', d3.forceCenter(width / 2, height / 2))
        .force('collision', d3.forceCollide().radius(30));

    const g = svgSelection.select('g');

    linkSelection = g.select('.links').selectAll('line')
        .data(edges, d => d.source.id + '-' + d.target.id);

    linkSelection.exit().remove();

    const linkEnter = linkSelection.enter()
        .append('line')
        .attr('marker-end', 'url(#arrowhead)')
        .on('click', (event, d) => {
            event.stopPropagation();
            showEdgeDetail(d);
        });

    linkSelection = linkEnter.merge(linkSelection);

    linkSelection
        .attr('stroke', d => valenceColor(d.valence))
        .attr('stroke-width', d => Math.max(1, d.strength * 5 + 1))
        .attr('stroke-opacity', 0.7);

    nodeSelection = g.select('.nodes').selectAll('circle')
        .data(nodes, d => d.id);

    nodeSelection.exit().remove();

    const nodeEnter = nodeSelection.enter()
        .append('circle')
        .attr('r', 16)
        .attr('fill', '#0f3460')
        .attr('stroke', '#4ecca3')
        .attr('stroke-width', 2)
        .on('click', (event, d) => {
            event.stopPropagation();
            selectAgent(d.id);
        })
        .call(d3.drag()
            .on('start', dragStarted)
            .on('drag', dragged)
            .on('end', dragEnded));

    nodeSelection = nodeEnter.merge(nodeSelection);

    nodeSelection
        .attr('fill', d => d.id === selectedAgent ? '#4ecca3' : '#0f3460')
        .attr('stroke', d => d.id === selectedAgent ? '#e0e0e0' : '#4ecca3');

    labelSelection = g.select('.labels').selectAll('text')
        .data(nodes, d => d.id);

    labelSelection.exit().remove();

    const labelEnter = labelSelection.enter()
        .append('text')
        .attr('class', 'node-label')
        .attr('dy', -22);

    labelSelection = labelEnter.merge(labelSelection);

    labelSelection.text(d => d.name);

    simulation.on('tick', () => {
        linkSelection
            .attr('x1', d => d.source.x)
            .attr('y1', d => d.source.y)
            .attr('x2', d => d.target.x)
            .attr('y2', d => d.target.y);

        nodeSelection
            .attr('cx', d => d.x)
            .attr('cy', d => d.y);

        labelSelection
            .attr('x', d => d.x)
            .attr('y', d => d.y);
    });
}

function dragStarted(event, d) {
    if (!event.active) simulation.alphaTarget(0.3).restart();
    d.fx = d.x;
    d.fy = d.y;
}

function dragged(event, d) {
    d.fx = event.x;
    d.fy = event.y;
}

function dragEnded(event, d) {
    if (!event.active) simulation.alphaTarget(0);
    d.fx = null;
    d.fy = null;
}

function initWebSocket() {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(protocol + '//' + window.location.host + '/ws');
    ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);
        handleWSMessage(msg);
    };
    ws.onclose = () => {
        setTimeout(initWebSocket, 3000);
    };
    ws.onerror = () => {
        ws.close();
    };
}

function handleWSMessage(msg) {
    switch (msg.type) {
        case 'agent_created':
        case 'agent_deleted':
        case 'bond_updated':
        case 'tick_completed':
        case 'scenario_loaded':
            loadGraph().then(() => {
                updateGraph();
                loadStats();
                loadAgentList();
                if (selectedAgent) loadAgentBonds(selectedAgent);
            });
            break;
    }
}

async function registerAgent() {
    const name = document.getElementById('agentName').value.trim();
    const description = document.getElementById('agentDesc').value.trim();
    if (!name) return;

    const resp = await fetch('/api/agents', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, description })
    });

    if (resp.ok) {
        document.getElementById('agentName').value = '';
        document.getElementById('agentDesc').value = '';
        await loadGraph();
        updateGraph();
        loadStats();
        loadAgentList();
    } else {
        const err = await resp.json();
        alert(err.detail || '注册失败');
    }
}

async function deleteAgent(agentId) {
    if (!confirm('确定删除此 Agent？')) return;

    const resp = await fetch('/api/agents/' + agentId, {
        method: 'DELETE'
    });

    if (resp.ok) {
        if (selectedAgent === agentId) {
            selectedAgent = null;
            document.getElementById('bondDetail').innerHTML = '<p class="placeholder-text">点击图谱节点查看羁绊详情</p>';
            document.getElementById('eventForm').style.display = 'none';
        }
        await loadGraph();
        updateGraph();
        loadStats();
        loadAgentList();
    }
}

async function loadAgentList() {
    const resp = await fetch('/api/agents');
    const agents = await resp.json();

    const listEl = document.getElementById('agentList');
    listEl.innerHTML = '';

    agents.forEach(agent => {
        const item = document.createElement('div');
        item.className = 'agent-item' + (agent.id === selectedAgent ? ' selected' : '');
        item.innerHTML = `
            <div class="agent-item-info">
                <span class="agent-item-name">${escapeHtml(agent.name)}</span>
                <span class="agent-item-desc">${escapeHtml(agent.description || '')}</span>
            </div>
            <button class="btn-delete" onclick="event.stopPropagation(); deleteAgent('${agent.id}')">×</button>
        `;
        item.addEventListener('click', () => selectAgent(agent.id));
        listEl.appendChild(item);
    });
}

function selectAgent(agentId) {
    selectedAgent = agentId;
    loadAgentBonds(agentId);
    updateGraph();
    loadAgentList();
}

async function loadAgentBonds(agentId) {
    const resp = await fetch('/api/agents/' + agentId + '/bonds');
    const bonds = await resp.json();

    const detailEl = document.getElementById('bondDetail');
    detailEl.innerHTML = '';

    if (bonds.length === 0) {
        detailEl.innerHTML = '<p class="placeholder-text">该 Agent 暂无羁绊</p>';
    } else {
        const listDiv = document.createElement('div');
        listDiv.className = 'bond-list';

        bonds.forEach(bond => {
            const item = document.createElement('div');
            item.className = 'bond-item';
            const valenceClass = bond.valence > 0.1 ? 'valence-positive' : bond.valence < -0.1 ? 'valence-negative' : 'valence-neutral';
            item.innerHTML = `
                <div class="bond-item-header">
                    <span class="bond-target">${escapeHtml(bond.target_name || bond.target_id)}</span>
                    <span class="bond-type">${escapeHtml(bond.type || 'stranger')}</span>
                </div>
                <div class="bond-values">
                    <span class="${valenceClass}">效价: ${formatValue(bond.valence)}</span>
                    <span>信任: ${formatValue(bond.trust)}</span>
                    <span>强度: ${formatValue(bond.strength)}</span>
                </div>
            `;
            item.addEventListener('click', () => showBondDetail(bond));
            listDiv.appendChild(item);
        });

        detailEl.appendChild(listDiv);
    }

    const formEl = document.getElementById('eventForm');
    formEl.style.display = 'block';

    const targetSelect = document.getElementById('eventTarget');
    targetSelect.innerHTML = '';
    graphData.nodes.forEach(node => {
        if (node.id !== agentId) {
            const opt = document.createElement('option');
            opt.value = node.id;
            opt.textContent = node.name;
            targetSelect.appendChild(opt);
        }
    });
}

function showBondDetail(bond) {
    const detailEl = document.getElementById('bondDetail');
    const listEl = detailEl.querySelector('.bond-list');

    const panel = document.createElement('div');
    panel.className = 'bond-detail-panel';

    const valenceClass = bond.valence > 0.1 ? 'valence-positive' : bond.valence < -0.1 ? 'valence-negative' : 'valence-neutral';

    let html = `
        <div class="detail-row"><span class="detail-label">目标</span><span class="detail-value">${escapeHtml(bond.target_name || bond.target_id)}</span></div>
        <div class="detail-row"><span class="detail-label">类型</span><span class="detail-value">${escapeHtml(bond.type || 'stranger')}</span></div>
        <div class="detail-row"><span class="detail-label">效价</span><span class="detail-value ${valenceClass}">${formatValue(bond.valence)}</span></div>
        <div class="detail-row"><span class="detail-label">信任</span><span class="detail-value">${formatValue(bond.trust)}</span></div>
        <div class="detail-row"><span class="detail-label">强度</span><span class="detail-value">${formatValue(bond.strength)}</span></div>
        <div class="detail-row"><span class="detail-label">稳定性</span><span class="detail-value">${formatValue(bond.stability)}</span></div>
        <div class="detail-row"><span class="detail-label">可见性</span><span class="detail-value">${escapeHtml(bond.visibility || 'private')}</span></div>
    `;

    if (bond.emotions && bond.emotions.length > 0) {
        html += '<div class="emotion-list">';
        bond.emotions.forEach(em => {
            html += `<div class="emotion-item"><span>${escapeHtml(em.type)}</span><span>强度: ${formatValue(em.intensity)}</span></div>`;
        });
        html += '</div>';
    }

    panel.innerHTML = html;

    const existingPanel = detailEl.querySelector('.bond-detail-panel');
    if (existingPanel) existingPanel.remove();

    if (listEl) {
        detailEl.insertBefore(panel, listEl);
    } else {
        detailEl.appendChild(panel);
    }
}

function showEdgeDetail(edge) {
    const sourceNode = graphData.nodes.find(n => n.id === edge.source || (edge.source.id && n.id === edge.source.id));
    const targetNode = graphData.nodes.find(n => n.id === edge.target || (edge.target.id && n.id === edge.target.id));
    const sourceName = sourceNode ? sourceNode.name : (edge.source.id || edge.source);
    const targetName = targetNode ? targetNode.name : (edge.target.id || edge.target);

    const valenceClass = edge.valence > 0.1 ? 'valence-positive' : edge.valence < -0.1 ? 'valence-negative' : 'valence-neutral';

    const detailEl = document.getElementById('bondDetail');
    detailEl.innerHTML = '';

    const panel = document.createElement('div');
    panel.className = 'bond-detail-panel';

    let html = `
        <div class="detail-row"><span class="detail-label">源</span><span class="detail-value">${escapeHtml(sourceName)}</span></div>
        <div class="detail-row"><span class="detail-label">目标</span><span class="detail-value">${escapeHtml(targetName)}</span></div>
        <div class="detail-row"><span class="detail-label">类型</span><span class="detail-value">${escapeHtml(edge.type || 'stranger')}</span></div>
        <div class="detail-row"><span class="detail-label">效价</span><span class="detail-value ${valenceClass}">${formatValue(edge.valence)}</span></div>
        <div class="detail-row"><span class="detail-label">信任</span><span class="detail-value">${formatValue(edge.trust)}</span></div>
        <div class="detail-row"><span class="detail-label">强度</span><span class="detail-value">${formatValue(edge.strength)}</span></div>
        <div class="detail-row"><span class="detail-label">稳定性</span><span class="detail-value">${formatValue(edge.stability)}</span></div>
        <div class="detail-row"><span class="detail-label">可见性</span><span class="detail-value">${escapeHtml(edge.visibility || 'private')}</span></div>
    `;

    if (edge.emotions && edge.emotions.length > 0) {
        html += '<div class="emotion-list">';
        edge.emotions.forEach(em => {
            html += `<div class="emotion-item"><span>${escapeHtml(em.type)}</span><span>强度: ${formatValue(em.intensity)}</span></div>`;
        });
        html += '</div>';
    }

    panel.innerHTML = html;
    detailEl.appendChild(panel);

    document.getElementById('eventForm').style.display = 'none';
}

async function emitEvent() {
    if (!selectedAgent) return;

    const targetId = document.getElementById('eventTarget').value;
    const eventType = document.getElementById('eventType').value;
    const description = document.getElementById('eventDescription').value.trim();
    const impactValence = parseFloat(document.getElementById('impactValence').value);
    const impactTrust = parseFloat(document.getElementById('impactTrust').value);

    if (!targetId || !description) {
        alert('请选择目标并填写事件描述');
        return;
    }

    const resp = await fetch('/api/agents/' + selectedAgent + '/events', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            target_id: targetId,
            event_type: eventType,
            description: description,
            impact_valence: impactValence,
            impact_trust: impactTrust,
            impact_strength: 0.0
        })
    });

    if (resp.ok) {
        document.getElementById('eventDescription').value = '';
        document.getElementById('impactValence').value = 0;
        document.getElementById('impactTrust').value = 0;
        document.getElementById('impactValenceValue').textContent = '0.0';
        document.getElementById('impactTrustValue').textContent = '0.0';
        await loadGraph();
        updateGraph();
        loadStats();
        loadAgentBonds(selectedAgent);
    } else {
        const err = await resp.json();
        alert(err.detail || '事件提交失败');
    }
}

async function loadStats() {
    const resp = await fetch('/api/network/stats');
    const stats = await resp.json();

    document.getElementById('statAgentCount').textContent = stats.agent_count || 0;
    document.getElementById('statBondCount').textContent = stats.bond_count || 0;
    document.getElementById('statEmotionCount').textContent = stats.active_emotion_count || 0;
    document.getElementById('statAvgValence').textContent = formatValue(stats.avg_valence || 0);
    document.getElementById('statAvgTrust').textContent = formatValue(stats.avg_trust || 0);
}

function valenceColor(v) {
    if (v > 0.1) return '#4ecca3';
    if (v < -0.1) return '#e74c3c';
    return '#95a5a6';
}

function formatValue(v) {
    if (v === null || v === undefined) return '0.00';
    return parseFloat(v).toFixed(2);
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

document.getElementById('impactValence').addEventListener('input', function () {
    document.getElementById('impactValenceValue').textContent = parseFloat(this.value).toFixed(1);
});

document.getElementById('impactTrust').addEventListener('input', function () {
    document.getElementById('impactTrustValue').textContent = parseFloat(this.value).toFixed(1);
});

window.addEventListener('resize', () => {
    if (simulation) {
        const container = document.getElementById('forceGraph');
        simulation.force('center', d3.forceCenter(container.clientWidth / 2, container.clientHeight / 2));
        simulation.alpha(0.3).restart();
    }
});

async function loadScenario(name) {
    const btn = event.target;
    btn.disabled = true;
    btn.textContent = '加载中...';
    
    try {
        const resp = await fetch('/api/scenarios/' + name, { method: 'POST' });
        if (resp.ok) {
            const result = await resp.json();
            selectedAgent = null;
            document.getElementById('bondDetail').innerHTML = '<p class="placeholder-text">点击图谱节点查看羁绊详情</p>';
            document.getElementById('eventForm').style.display = 'none';
            await loadGraph();
            updateGraph();
            loadStats();
            loadAgentList();
        } else {
            const err = await resp.json();
            alert(err.detail || '加载场景失败');
        }
    } finally {
        btn.disabled = false;
        btn.textContent = name === 'simple' ? '简单' : name === 'medium' ? '中等' : name === 'complex' ? '复杂' : '超复杂';
    }
}

async function clearAll() {
    if (!confirm('确定清空所有数据？')) return;
    
    const resp = await fetch('/api/agents');
    const agents = await resp.json();
    
    for (const agent of agents) {
        await fetch('/api/agents/' + agent.id, { method: 'DELETE' });
    }
    
    selectedAgent = null;
    document.getElementById('bondDetail').innerHTML = '<p class="placeholder-text">点击图谱节点查看羁绊详情</p>';
    document.getElementById('eventForm').style.display = 'none';
    await loadGraph();
    updateGraph();
    loadStats();
    loadAgentList();
}

init();

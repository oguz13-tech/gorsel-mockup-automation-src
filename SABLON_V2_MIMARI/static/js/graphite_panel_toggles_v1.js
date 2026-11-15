/* Graphite V5 independent review-panel toggles.
 * Presentation only: all existing canvas, mask, approval and save handlers
 * remain mounted.  Collapsing a panel only changes its layout footprint. */
(() => {
  'use strict';
  const body = document.body;
  const read = (key) => {
    try { return window.localStorage.getItem(key) === '1'; }
    catch (_ignored) { return false; }
  };
  const write = (key, value) => {
    try { window.localStorage.setItem(key, value ? '1' : '0'); }
    catch (_ignored) { /* Session state still works when storage is disabled. */ }
  };
  const fireResize = () => {
    window.dispatchEvent(new Event('resize'));
    window.requestAnimationFrame(() => window.dispatchEvent(new Event('resize')));
  };

  function setToolsCollapsed(collapsed, persist = true) {
    body.classList.toggle('graphite-tools-collapsed', collapsed);
    const button = document.getElementById('rightPanelToggle');
    if (button) {
      button.textContent = collapsed ? '◀' : '▶';
      button.title = collapsed ? '4 Köşe / PETEK araçlarını genişlet' : '4 Köşe / PETEK araçlarını daralt';
      button.setAttribute('aria-label', button.title);
      button.setAttribute('aria-expanded', String(!collapsed));
    }
    if (persist) write('graphite.review.tools.collapsed', collapsed);
    fireResize();
  }

  function setFlowCollapsed(collapsed, persist = true) {
    body.classList.toggle('graphite-flow-collapsed', collapsed);
    const panel = document.getElementById('graphiteFlowPanel');
    const inline = document.getElementById('graphiteFlowToggle');
    const open = document.getElementById('graphiteFlowOpen');
    if (panel) panel.setAttribute('aria-hidden', String(collapsed));
    if (inline) {
      inline.textContent = collapsed ? '▲' : '▼';
      inline.title = collapsed ? 'Alt görsel akışını genişlet' : 'Alt görsel akışını daralt';
      inline.setAttribute('aria-expanded', String(!collapsed));
    }
    if (open) {
      open.hidden = !collapsed;
      open.setAttribute('aria-expanded', String(!collapsed));
    }
    if (persist) write('graphite.review.flow.collapsed', collapsed);
    fireResize();
  }

  function refreshFlow() {
    const status = document.getElementById('graphiteFlowStatus');
    const current = document.getElementById('current-file');
    const source = document.getElementById('source-view-status');
    if (!status) return;
    const name = current?.textContent?.trim();
    const mode = source?.textContent?.trim();
    status.textContent = name && name !== 'Görsel Seçin'
      ? `${name}${mode ? ' · ' + mode.replace(/\s+/g, ' ') : ''}`
      : 'Gerçek editör görünümü';
    const selected = (window.sourceViewMode || 'working').toLowerCase();
    document.querySelectorAll('.graphite-flow-step').forEach(step => {
      step.classList.toggle('is-active', step.dataset.flowSource === selected ||
        (selected === 'preview' && step.dataset.flowSource === 'design'));
    });
  }

  function init() {
    const right = document.getElementById('rightPanelToggle');
    if (right) right.addEventListener('click', () =>
      setToolsCollapsed(!body.classList.contains('graphite-tools-collapsed')));

    const flowToggle = document.getElementById('graphiteFlowToggle');
    const flowOpen = document.getElementById('graphiteFlowOpen');
    if (flowToggle) flowToggle.addEventListener('click', () =>
      setFlowCollapsed(!body.classList.contains('graphite-flow-collapsed')));
    if (flowOpen) flowOpen.addEventListener('click', () => setFlowCollapsed(false));

    setToolsCollapsed(read('graphite.review.tools.collapsed'), false);
    setFlowCollapsed(read('graphite.review.flow.collapsed'), false);
    refreshFlow();
    const observer = new MutationObserver(refreshFlow);
    ['current-file', 'source-view-status'].forEach(id => {
      const node = document.getElementById(id);
      if (node) observer.observe(node, {childList: true, subtree: true, characterData: true});
    });
    window.addEventListener('resize', refreshFlow);
    window.graphiteRefreshFlow = refreshFlow;
  }
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, {once: true});
  else init();
})();

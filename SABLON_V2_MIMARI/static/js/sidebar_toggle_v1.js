/* Graphite V5 main-navigation collapse. Presentation/layout only. */
(() => {
  'use strict';

  const STORAGE_KEY = 'graphite.template-list.collapsed';
  const LEGACY_STORAGE_KEY = 'graphite.sidebar.collapsed';
  const TRANSITION_MS = 220;

  function safeGetCollapsed() {
    try {
      const current = window.localStorage.getItem(STORAGE_KEY);
      return current === '1' || (current === null && window.localStorage.getItem(LEGACY_STORAGE_KEY) === '1');
    }
    catch (_ignored) { return false; }
  }

  function safeSetCollapsed(collapsed) {
    try { window.localStorage.setItem(STORAGE_KEY, collapsed ? '1' : '0'); }
    catch (_ignored) { /* Private browsing/storage-disabled: keep this session state. */ }
  }

  function readWidth(sidebar) {
    const width = Number.parseFloat(window.getComputedStyle(sidebar).width);
    return Number.isFinite(width) && width > 0 ? Math.round(width) : 205;
  }

  function updateButton(button, collapsed) {
    button.textContent = collapsed ? '▶' : '◀';
    button.title = collapsed ? 'Şablon listesini genişlet' : 'Şablon listesini daralt';
    button.setAttribute('aria-label', button.title);
    button.setAttribute('aria-expanded', String(!collapsed));
  }

  function notifyLayoutChange() {
    // Existing canvas/PETEK code already listens to resize; no engine or data
    // endpoint is involved in this presentation-only reflow.
    window.dispatchEvent(new Event('resize'));
  }

  function setCollapsed(collapsed, sidebar, button, resizer, persist) {
    if (!collapsed) {
      const savedWidth = Number.parseFloat(sidebar.dataset.graphiteExpandedWidth);
      const restoreWidth = Number.isFinite(savedWidth) && savedWidth > 0 ? savedWidth : 205;
      sidebar.dataset.graphiteExpandedWidth = String(Math.round(restoreWidth));
      sidebar.style.setProperty('width', `${Math.round(restoreWidth)}px`, 'important');
    } else {
      // Capture the actual current width as well as the layout-editor width;
      // the legacy drag handle can resize this panel without touching the
      // review-layout preferences object.
      const currentWidth = readWidth(sidebar);
      if (currentWidth > 0) sidebar.dataset.graphiteExpandedWidth = String(currentWidth);
    }

    document.body.classList.toggle('graphite-sidebar-collapsed', collapsed);
    sidebar.classList.toggle('is-collapsed', collapsed);
    resizer?.classList.toggle('is-collapsed', collapsed);
    if (collapsed) sidebar.style.setProperty('width', '0px', 'important');
    updateButton(button, collapsed);
    if (persist) safeSetCollapsed(collapsed);

    window.requestAnimationFrame(() => {
      notifyLayoutChange();
      window.setTimeout(notifyLayoutChange, TRANSITION_MS);
    });
  }

  function init() {
    const sidebar = document.getElementById('sidebar');
    const button = document.getElementById('sidebarToggle');
    const resizer = document.getElementById('resizer-left');
    if (!sidebar || !button) return;

    const collapsed = safeGetCollapsed();
    if (!collapsed) sidebar.dataset.graphiteExpandedWidth = String(readWidth(sidebar));
    button.addEventListener('click', () => {
      setCollapsed(!document.body.classList.contains('graphite-sidebar-collapsed'),
        sidebar, button, resizer, true);
    });
    if (collapsed) {
      // Do not snapshot the pre-editor CSS width here. The deferred Graphite
      // layout loader will provide the user's real expanded width.
      document.body.classList.add('graphite-sidebar-collapsed');
      sidebar.classList.add('is-collapsed');
      resizer?.classList.add('is-collapsed');
      sidebar.style.setProperty('width', '0px', 'important');
      updateButton(button, true);
    } else {
      setCollapsed(false, sidebar, button, resizer, false);
    }
  }

  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', init, {once: true});
  else init();
})();

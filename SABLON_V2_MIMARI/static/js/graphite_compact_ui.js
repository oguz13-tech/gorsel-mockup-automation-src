/* Compact Graphite controls: presentation-only state, no geometry or data rewrite. */
(function () {
  'use strict';
  window.pauseReview = function () {
    var status = document.getElementById('graphiteActionStatus');
    var dock = document.getElementById('graphiteActionDock');
    var paused = dock && dock.classList.toggle('is-paused');
    if (status) status.textContent = paused ? 'İnceleme beklemeye alındı.' : 'İnceleme devam ediyor.';
  };
})();

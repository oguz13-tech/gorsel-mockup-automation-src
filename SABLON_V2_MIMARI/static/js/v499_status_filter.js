/* V4.9.9 presentation filter only: no writes to profiles, mask or DB. */
(function(){'use strict';
 const statuses=new Set(['NEW','APPROVED','DRAFT','ERROR']);
 function selected(){const inputs=[...document.querySelectorAll('[data-v499-state]')];
   return new Set(inputs.filter(x=>x.checked).map(x=>x.dataset.v499State).filter(x=>statuses.has(x)));}
 function allowed(st){return selected().has(st);}
 function applyRow(row){if(row?.dataset?.v499Status) row.hidden=!allowed(row.dataset.v499Status);}
 function apply(){document.querySelectorAll('.template-item[data-v499-status]').forEach(applyRow);
   document.dispatchEvent(new CustomEvent('v499:status-filter'));}
 function init(){document.querySelectorAll('[data-v499-state]').forEach(x=>x.addEventListener('change',apply));apply();}
 window.V499StatusFilters={allowed,applyRow,apply,selected};
 if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',init);else init();
})();

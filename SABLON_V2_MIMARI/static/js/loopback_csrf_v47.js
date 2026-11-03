/* Process-secret anti-CSRF for existing editor fetch callers; no API rewrite.
   All API mutations go through same-origin fetch with CSRF header. */
(() => {
  'use strict';
  const original = window.fetch.bind(window);
  let secretPromise;
  function token() {
    if (!secretPromise) {
      secretPromise = original('/api/session/csrf', {cache:'no-store', credentials:'same-origin'})
        .then(r => { if (!r.ok) throw new Error('CSRF_UNAVAILABLE'); return r.json(); })
        .then(x => {if (typeof x.csrf !== 'string') throw new Error('CSRF_INVALID');return x.csrf;});
    }
    return secretPromise;
  }
  window.fetch = async (input, options={}) => {
    const url = typeof input === 'string' ? input : input.url;
    const urlObj = new URL(url, window.location.href);
    const method = (options.method || (typeof input !== 'string' && input.method) || 'GET').toUpperCase();
    if (urlObj.origin !== window.location.origin || !['POST','PUT','PATCH','DELETE'].includes(method))
      return original(input, options);
    const headers = new Headers(options.headers || (typeof input !== 'string' ? input.headers : undefined));
    headers.set('X-V47-CSRF', await token());
    return original(input, {...options, headers, credentials: 'same-origin'});
  };
})();

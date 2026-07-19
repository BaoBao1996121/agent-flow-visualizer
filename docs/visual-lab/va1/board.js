const candidates = new Set(['field-manual', 'blueprint', 'miniature']);
const params = new URLSearchParams(window.location.search);
const view = params.get('view') === 'focus' ? 'focus' : 'compare';
const requestedCandidate = params.get('candidate');
const candidate = candidates.has(requestedCandidate) ? requestedCandidate : 'field-manual';

document.body.dataset.view = view;
document.body.dataset.activeCandidate = candidate;

for (const panel of document.querySelectorAll('[data-candidate]')) {
  panel.dataset.selected = String(panel.dataset.candidate === candidate);
}

for (const link of document.querySelectorAll('[data-view-link]')) {
  link.setAttribute('aria-current', link.dataset.viewLink === view ? 'page' : 'false');
}

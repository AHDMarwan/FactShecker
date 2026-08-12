const state = { data: null, query: '', status: 'all', language: 'all' };

const labels = {
  needs_review: 'تحتاج مراجعة',
  medium_evidence: 'أدلة متوسطة',
  corroborated: 'مدعومة بعدة مصادر',
};

const $ = (id) => document.getElementById(id);

function formatDate(value) {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return new Intl.DateTimeFormat('ar-MA', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date);
}

function escapeHtml(value = '') {
  return value.replace(/[&<>'"]/g, (char) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', "'": '&#39;', '"': '&quot;'
  }[char]));
}

function scorePercent(score) {
  return Math.round((Number(score) || 0) * 100);
}

function matches(item) {
  const haystack = [
    item.title,
    ...(item.sources || []),
    ...(item.articles || []).map((article) => article.title),
  ].join(' ').toLowerCase();

  if (state.query && !haystack.includes(state.query.toLowerCase())) return false;
  if (state.status !== 'all' && item.status !== state.status) return false;
  if (state.language !== 'all' && !(item.languages || []).includes(state.language)) return false;
  return true;
}

function card(item) {
  const sources = (item.sources || []).slice(0, 4).map((source) => `<span>${escapeHtml(source)}</span>`).join('');
  const articles = (item.articles || []).slice(0, 5).map((article) => `
    <li>
      <a href="${escapeHtml(article.url)}" target="_blank" rel="noreferrer">${escapeHtml(article.title)}</a>
      <small>${escapeHtml(article.source?.name || 'مصدر غير محدد')} · ${formatDate(article.published_at)}</small>
    </li>
  `).join('');

  return `
    <article class="news-card">
      <div class="card-top">
        <span class="status status-${escapeHtml(item.status)}">${labels[item.status] || escapeHtml(item.status)}</span>
        ${item.claim_candidate ? '<span class="claim-badge">ادعاء قابل للفحص</span>' : ''}
      </div>
      <h3>${escapeHtml(item.title)}</h3>
      <div class="meta">
        <span>${item.source_count || 0} مصادر</span>
        <span>${item.article_count || 0} تغطيات</span>
        <span>${(item.languages || []).join(' / ').toUpperCase()}</span>
      </div>
      <div class="evidence">
        <div class="evidence-head">
          <span>دعم الأدلة المرصودة</span>
          <strong>${scorePercent(item.evidence_score)}%</strong>
        </div>
        <div class="meter"><span style="width:${scorePercent(item.evidence_score)}%"></span></div>
      </div>
      <div class="source-tags">${sources}</div>
      <details>
        <summary>عرض التغطيات والمصادر</summary>
        <ul class="article-list">${articles}</ul>
      </details>
    </article>
  `;
}

function render() {
  if (!state.data) return;
  const items = (state.data.items || []).filter(matches);
  $('resultsCount').textContent = `${items.length} نتيجة`;
  $('feed').innerHTML = items.map(card).join('');
  $('emptyState').hidden = items.length !== 0;
}

function renderStats() {
  const stats = state.data?.stats || {};
  $('articlesCount').textContent = stats.articles ?? 0;
  $('clustersCount').textContent = stats.clusters ?? 0;
  $('sourcesCount').textContent = stats.sources ?? 0;
  $('reviewCount').textContent = stats.needs_review ?? 0;
  $('generatedAt').textContent = formatDate(state.data?.generated_at);
}

async function load() {
  try {
    const response = await fetch('./data/index.json', { cache: 'no-store' });
    if (!response.ok) throw new Error(`HTTP ${response.status}`);
    state.data = await response.json();
    renderStats();
    render();
  } catch (error) {
    $('feed').innerHTML = `<div class="error">تعذر تحميل البيانات: ${escapeHtml(error.message)}</div>`;
  }
}

$('searchInput').addEventListener('input', (event) => {
  state.query = event.target.value.trim();
  render();
});
$('statusFilter').addEventListener('change', (event) => {
  state.status = event.target.value;
  render();
});
$('languageFilter').addEventListener('change', (event) => {
  state.language = event.target.value;
  render();
});

load();

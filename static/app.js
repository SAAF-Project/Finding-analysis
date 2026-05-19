/* ══════════════════════════════════════════════════════════
   Multimodal Audit Intelligence Agent — Frontend Logic
   ══════════════════════════════════════════════════════════ */

'use strict';

// ── State ──────────────────────────────────────────────────────────────────
let selectedFiles = [];
let engagementFile = null;
let currentUploadId = null;
let tokenCount = 0;

// ── DOM references ──────────────────────────────────────────────────────────
const dropZone    = document.getElementById('drop-zone');
const fileInput   = document.getElementById('file-input');
const fileList    = document.getElementById('file-list');
const yearSlider  = document.getElementById('lookback-years');
const yearsDisplay= document.getElementById('years-display');
const apiKeyInput = document.getElementById('api-key');
const toggleKey   = document.getElementById('toggle-key');
const analyzeBtn  = document.getElementById('analyze-btn');

const elDropZone    = document.getElementById('el-drop-zone');
const engagementInput = document.getElementById('engagement-input');
const engagementFilename = document.getElementById('engagement-filename');
const engagementName = document.getElementById('engagement-name');
const engagementRemove = document.getElementById('engagement-remove');

const uploadSection   = document.getElementById('upload-section');
const progressSection = document.getElementById('progress-section');
const progressSteps   = document.getElementById('progress-steps');
const thinkingBox     = document.getElementById('thinking-box');
const thinkingText    = document.getElementById('thinking-text');
const streamBox       = document.getElementById('stream-box');
const streamText      = document.getElementById('stream-text');
const tokenCountEl    = document.getElementById('token-count');

const reportSection  = document.getElementById('report-section');
const reportContent  = document.getElementById('report-content');
const downloadHtml   = document.getElementById('download-html');
const downloadDocx   = document.getElementById('download-docx');
const downloadPdf    = document.getElementById('download-pdf');
const newAnalysisBtn = document.getElementById('new-analysis');

// ── Tabs ────────────────────────────────────────────────────────────────────
document.querySelectorAll('.tab-btn').forEach(btn => {
  btn.addEventListener('click', () => {
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('tab-active'));
    document.querySelectorAll('.tab-panel').forEach(p => p.classList.add('hidden'));
    btn.classList.add('tab-active');
    document.getElementById('tab-' + btn.dataset.tab).classList.remove('hidden');
    updateAnalyzeBtn();
  });
});

// SharePoint fields
const spFields = ['sp-site-url', 'sp-folder', 'sp-username', 'sp-password'];
spFields.forEach(id => {
  document.getElementById(id).addEventListener('input', updateAnalyzeBtn);
});

function getSpValues() {
  return spFields.map(id => document.getElementById(id).value.trim());
}
function allSpFilled() {
  return getSpValues().every(Boolean);
}

// ── File icons ─────────────────────────────────────────────────────────────
function fileIcon(name) {
  const ext = (name.split('.').pop() || '').toLowerCase();
  return { pdf: '📄', pptx: '📊', xlsx: '📈', xls: '📈', docx: '📝',
           png: '🖼', jpg: '🖼', jpeg: '🖼', gif: '🖼', webp: '🖼' }[ext] || '📎';
}

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

function escHtml(str) {
  return String(str).replace(/[&<>"']/g, c =>
    ({ '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;' }[c]));
}

// ── Analyze button state ────────────────────────────────────────────────────
function updateAnalyzeBtn() {
  const activeTab = document.querySelector('.tab-btn.tab-active')?.dataset?.tab;
  const hasFiles = selectedFiles.length > 0;
  const hasSP = activeTab === 'sharepoint' && allSpFilled();
  const hasKey = !!apiKeyInput.value.trim();
  analyzeBtn.disabled = !(hasFiles || hasSP) || !hasKey;
}

// ── Local file management ──────────────────────────────────────────────────
function addFiles(newFiles) {
  for (const file of newFiles) {
    if (!selectedFiles.some(f => f.name === file.name && f.size === file.size)) {
      selectedFiles.push(file);
    }
  }
  renderFileList();
}

function removeFile(index) {
  selectedFiles.splice(index, 1);
  renderFileList();
}

function renderFileList() {
  if (selectedFiles.length === 0) {
    fileList.classList.add('hidden');
    updateAnalyzeBtn();
    return;
  }
  fileList.classList.remove('hidden');
  fileList.innerHTML = selectedFiles.map((f, i) => `
    <div class="file-item">
      <span class="file-icon">${fileIcon(f.name)}</span>
      <span class="file-name">${escHtml(f.name)}</span>
      <span class="file-size">${formatSize(f.size)}</span>
      <button class="file-remove" onclick="removeFile(${i})" title="Verwijder">✕</button>
    </div>
  `).join('');
  updateAnalyzeBtn();
}

// ── Local drop zone events ─────────────────────────────────────────────────
dropZone.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', () => { addFiles(fileInput.files); fileInput.value = ''; });
dropZone.addEventListener('dragover', e => { e.preventDefault(); dropZone.classList.add('drag-over'); });
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
dropZone.addEventListener('drop', e => {
  e.preventDefault(); dropZone.classList.remove('drag-over');
  addFiles(e.dataTransfer.files);
});

// ── Engagement letter ──────────────────────────────────────────────────────
elDropZone.addEventListener('click', () => engagementInput.click());
engagementInput.addEventListener('change', () => {
  if (engagementInput.files[0]) setEngagementFile(engagementInput.files[0]);
});
elDropZone.addEventListener('dragover', e => { e.preventDefault(); elDropZone.classList.add('drag-over'); });
elDropZone.addEventListener('dragleave', () => elDropZone.classList.remove('drag-over'));
elDropZone.addEventListener('drop', e => {
  e.preventDefault(); elDropZone.classList.remove('drag-over');
  const f = e.dataTransfer.files[0];
  if (f) setEngagementFile(f);
});

function setEngagementFile(file) {
  engagementFile = file;
  engagementName.textContent = file.name;
  engagementFilename.classList.remove('hidden');
  elDropZone.style.display = 'none';
}

engagementRemove.addEventListener('click', () => {
  engagementFile = null;
  engagementInput.value = '';
  engagementFilename.classList.add('hidden');
  elDropZone.style.display = '';
});

// ── Slider ─────────────────────────────────────────────────────────────────
yearSlider.addEventListener('input', () => yearsDisplay.textContent = yearSlider.value);

// ── API key toggle ──────────────────────────────────────────────────────────
toggleKey.addEventListener('click', () => {
  const isText = apiKeyInput.type === 'text';
  apiKeyInput.type = isText ? 'password' : 'text';
  toggleKey.textContent = isText ? '👁' : '🙈';
});
apiKeyInput.addEventListener('input', updateAnalyzeBtn);

// ── Progress helpers ────────────────────────────────────────────────────────
function addProgressStep(msg, type = 'active') {
  const prev = progressSteps.querySelector('.step-active');
  if (prev) {
    prev.classList.remove('step-active');
    prev.classList.add('step-done');
    prev.querySelector('.step-spinner')?.remove();
    if (!prev.querySelector('.step-check')) {
      prev.insertAdjacentHTML('afterbegin', '<span class="step-check">✅ </span>');
    }
  }
  const div = document.createElement('div');
  div.className = `progress-step step-${type}`;
  const spinner = type === 'active' ? '<div class="step-spinner"></div>' : '';
  div.innerHTML = `${spinner}<span>${escHtml(msg)}</span>`;
  progressSteps.appendChild(div);
  div.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}

function setStepError(msg) {
  const last = progressSteps.lastElementChild;
  if (last) {
    last.classList.remove('step-active', 'step-done');
    last.classList.add('step-error');
    last.querySelector('.step-spinner')?.remove();
    last.innerHTML = `<span>❌ ${escHtml(msg)}</span>`;
  }
}

// ── Main analyse ────────────────────────────────────────────────────────────
analyzeBtn.addEventListener('click', startAnalysis);

async function startAnalysis() {
  const activeTab = document.querySelector('.tab-btn.tab-active')?.dataset?.tab;
  const hasFiles = selectedFiles.length > 0;
  const hasSP = activeTab === 'sharepoint' && allSpFilled();

  if ((!hasFiles && !hasSP) || !apiKeyInput.value.trim()) return;

  // Switch to progress view
  uploadSection.classList.add('hidden');
  progressSection.classList.remove('hidden');
  reportSection.classList.add('hidden');
  progressSteps.innerHTML = '';
  thinkingBox.classList.add('hidden');
  streamBox.classList.add('hidden');
  thinkingText.textContent = '';
  streamText.textContent = '';
  tokenCount = 0;

  const label = hasSP && !hasFiles ? 'SharePoint map ophalen...'
              : hasFiles && hasSP   ? `${selectedFiles.length} bestand(en) + SharePoint verwerken...`
              : `${selectedFiles.length} bestand(en) uploaden en verwerken...`;
  addProgressStep(label);

  // Build form data
  const formData = new FormData();
  for (const file of selectedFiles) formData.append('files[]', file);
  formData.append('lookback_years', yearSlider.value);
  formData.append('api_key', apiKeyInput.value.trim());

  // SharePoint
  if (hasSP) {
    const [siteUrl, folder, username, password] = getSpValues();
    formData.append('sp_site_url', siteUrl);
    formData.append('sp_folder',   folder);
    formData.append('sp_username', username);
    formData.append('sp_password', password);
  }

  // Engagement letter
  if (engagementFile) formData.append('engagement_letter', engagementFile);

  // Keywords
  const kw = document.getElementById('keywords').value.trim();
  if (kw) formData.append('keywords', kw);

  try {
    const response = await fetch('/analyze', { method: 'POST', body: formData });
    if (!response.ok) throw new Error(`Server fout: ${response.status}`);

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop();

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        const raw = line.slice(6).trim();
        if (!raw) continue;
        let event;
        try { event = JSON.parse(raw); } catch { continue; }
        handleStreamEvent(event);
      }
    }
  } catch (err) {
    setStepError(err.message);
    console.error(err);
  }
}

function handleStreamEvent(event) {
  switch (event.type) {
    case 'progress':
      addProgressStep(event.message);
      break;

    case 'thinking_start':
      thinkingBox.classList.remove('hidden');
      addProgressStep(event.message || 'Extended thinking actief...');
      break;

    case 'thinking':
      if (event.text) {
        thinkingText.textContent += event.text + ' ';
        thinkingText.scrollTop = thinkingText.scrollHeight;
      }
      break;

    case 'text_start':
      streamBox.classList.remove('hidden');
      addProgressStep(event.message || 'JSON rapport wordt gegenereerd...');
      break;

    case 'token':
      if (event.text) {
        streamText.textContent += event.text;
        streamText.scrollTop = streamText.scrollHeight;
        tokenCount += event.text.length;
        tokenCountEl.textContent = `~${Math.round(tokenCount / 4)} tokens`;
      }
      break;

    case 'done': {
      const last = progressSteps.lastElementChild;
      if (last) {
        last.classList.remove('step-active');
        last.classList.add('step-done');
        last.querySelector('.step-spinner')?.remove();
        if (!last.querySelector('.step-check'))
          last.insertAdjacentHTML('afterbegin', '<span class="step-check">✅ </span>');
      }
      addProgressStep('Rapport klaar!', 'done');
      currentUploadId = event.upload_id;
      renderReport(event.report);
      setTimeout(() => {
        progressSection.classList.add('hidden');
        reportSection.classList.remove('hidden');
        reportSection.scrollIntoView({ behavior: 'smooth' });
      }, 800);
      break;
    }

    case 'error':
      setStepError(event.message || 'Onbekende fout');
      console.error('Analyse fout:', event);
      break;
  }
}

// ── Overzicht renderer ──────────────────────────────────────────────────────
function renderReport(r) {
  const meta = r.metadata || {};
  let html = '';

  // Metadata balk
  const aantalBestanden = meta.bestanden_geanalyseerd || 0;
  const kijktermijn = meta.kijktermijn_jaren || 0;
  const datum = meta.analysedatum || '';
  html += `
  <div class="ov-meta-balk">
    <span>📁 ${aantalBestanden} bestand(en) geanalyseerd</span>
    <span>📅 Kijktermijn: ${kijktermijn} jaar</span>
    <span>🗓 ${datum}</span>
  </div>`;

  // Samenvatting
  if (r.samenvatting) {
    html += `
    <div class="ov-samenvatting">
      <strong>Samenvatting</strong>
      <p>${escHtml(r.samenvatting)}</p>
    </div>`;
  }

  // Relevante bevindingen
  if (r.bevindingen && r.bevindingen.length) {
    // Groepeer op prioriteit
    const hoog   = r.bevindingen.filter(b => b.prioriteit === 'Hoog');
    const middel = r.bevindingen.filter(b => b.prioriteit === 'Middel');
    const laag   = r.bevindingen.filter(b => b.prioriteit !== 'Hoog' && b.prioriteit !== 'Middel');

    html += `<div class="ov-sectie"><h3 class="ov-sectie-titel">Relevante bevindingen</h3>`;

    for (const [groep, items] of [['Hoog', hoog], ['Middel', middel], ['Laag', laag]]) {
      if (!items.length) continue;
      html += `<div class="ov-prio-label ov-prio-${groep}">${groep} prioriteit</div>`;
      for (const b of items) {
        html += `
        <div class="ov-bevinding ov-bev-${escHtml(groep)}">
          <div class="ov-bev-header">
            <span class="ov-bev-bron">📎 ${escHtml(b.bron || '')}</span>
            ${b.jaar ? `<span class="ov-bev-jaar">${escHtml(b.jaar)}</span>` : ''}
          </div>
          <div class="ov-bev-tekst">${escHtml(b.bevinding || '')}</div>
          <div class="ov-bev-relevantie">↳ ${escHtml(b.relevantie || '')}</div>
        </div>`;
      }
    }
    html += `</div>`;
  }

  // Aandachtspunten
  if (r.aandachtspunten && r.aandachtspunten.length) {
    html += `<div class="ov-sectie"><h3 class="ov-sectie-titel">Aandachtspunten voor de auditor</h3>`;
    for (const ap of r.aandachtspunten) {
      html += `
      <div class="ov-aandacht">
        <div class="ov-aandacht-titel">⚠ ${escHtml(ap.onderwerp || '')}</div>
        <div class="ov-aandacht-tekst">${escHtml(ap.toelichting || '')}</div>
      </div>`;
    }
    html += `</div>`;
  }

  reportContent.innerHTML = html;
}

// ── Downloads ───────────────────────────────────────────────────────────────
downloadHtml.addEventListener('click', () => {
  if (currentUploadId) window.location.href = `/download/${currentUploadId}/html`;
});
downloadDocx.addEventListener('click', () => {
  if (currentUploadId) window.location.href = `/download/${currentUploadId}/docx`;
});
downloadPdf.addEventListener('click', () => {
  if (currentUploadId) window.location.href = `/download/${currentUploadId}/pdf`;
});


newAnalysisBtn.addEventListener('click', () => {
  selectedFiles = [];
  engagementFile = null;
  currentUploadId = null;
  tokenCount = 0;
  fileList.innerHTML = '';
  fileList.classList.add('hidden');
  engagementFilename.classList.add('hidden');
  elDropZone.style.display = '';
  engagementInput.value = '';
  fileInput.value = '';
  document.getElementById('keywords').value = '';
  updateAnalyzeBtn();
  reportSection.classList.add('hidden');
  uploadSection.classList.remove('hidden');
  uploadSection.scrollIntoView({ behavior: 'smooth' });
});

// ── Initial state ───────────────────────────────────────────────────────────
updateAnalyzeBtn();

// ─── Auto "Copy bảng" button cho mọi .table-wrap ───
// Format TSV (tab-separated) → paste vào Excel/Sheets sẽ tự split column.
(() => {
  function cellToText(cell) {
    // Nếu cell chứa list link (vd "Trang nguồn (sample)" có <ul><li><a>)
    // → gom hết URL thành 1 chuỗi phân cách " | "
    const liLinks = cell.querySelectorAll('li a[href]');
    if (liLinks.length > 0) {
      const urls = [...liLinks]
        .map((a) => (a.href || a.textContent || '').trim())
        .filter(Boolean);
      if (urls.length) return urls.join(' | ');
    }
    // Cell có nhiều <a> (vd image gallery, link sources)
    const allLinks = cell.querySelectorAll('a[href]');
    if (allLinks.length > 1) {
      const urls = [...allLinks]
        .map((a) => (a.href || a.textContent || '').trim())
        .filter(Boolean);
      if (urls.length) return urls.join(' | ');
    }
    // Default: innerText
    return (cell.innerText || cell.textContent || '').trim();
  }

  function tableToTSV(table) {
    // Force expand mọi <details> để innerText include content bên trong
    const detailsToRestore = [];
    table.querySelectorAll('details').forEach((d) => {
      if (!d.open) {
        detailsToRestore.push(d);
        d.open = true;
      }
    });

    const rows = [];
    table.querySelectorAll('tr').forEach((tr) => {
      const cells = [...tr.querySelectorAll('th, td')].map((cell) => {
        let text = cellToText(cell);
        text = text.replace(/[\t\r\n]+/g, ' ').replace(/\s+/g, ' ');
        return text;
      });
      if (cells.length) rows.push(cells.join('\t'));
    });

    // Restore <details> state
    detailsToRestore.forEach((d) => { d.open = false; });

    return rows.join('\n');
  }

  async function copyToClipboard(text) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      await navigator.clipboard.writeText(text);
      return;
    }
    // Fallback: textarea + execCommand
    const ta = document.createElement('textarea');
    ta.value = text;
    ta.style.position = 'fixed';
    ta.style.opacity = '0';
    document.body.appendChild(ta);
    ta.select();
    document.execCommand('copy');
    document.body.removeChild(ta);
  }

  function attachCopyButton(wrap) {
    if (wrap.dataset.copyAdded === '1') return;
    wrap.dataset.copyAdded = '1';

    const table = wrap.querySelector('table');
    if (!table) return;
    const rowCount = table.querySelectorAll('tbody tr').length;
    if (rowCount === 0) return;

    // Tạo action bar phía trên wrap
    const bar = document.createElement('div');
    bar.className = 'table-actions';

    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'btn btn-sm btn-ghost copy-table-btn';
    btn.innerHTML = '📋 Copy bảng (' + rowCount + ' dòng)';
    btn.title = 'Copy nội dung bảng dạng TSV để paste vào Excel / Google Sheets';
    btn.addEventListener('click', async () => {
      try {
        const tsv = tableToTSV(table);
        await copyToClipboard(tsv);
        const orig = btn.innerHTML;
        btn.innerHTML = '✅ Đã copy — paste Excel ngay được';
        btn.classList.add('copy-success');
        setTimeout(() => {
          btn.innerHTML = orig;
          btn.classList.remove('copy-success');
        }, 2000);
      } catch (err) {
        btn.innerHTML = '❌ Lỗi: ' + (err.message || err);
        setTimeout(() => {
          btn.innerHTML = '📋 Copy bảng (' + rowCount + ' dòng)';
        }, 3000);
      }
    });

    bar.appendChild(btn);
    wrap.parentNode.insertBefore(bar, wrap);
  }

  function init() {
    document.querySelectorAll('.table-wrap').forEach(attachCopyButton);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();

// ─── Sidebar group collapse/expand toggle (nhớ trạng thái mở/đóng) ───
(() => {
  const KEY = 'sb_open_groups';
  let openSet;
  try { openSet = new Set(JSON.parse(localStorage.getItem(KEY) || '[]')); } catch (e) { openSet = new Set(); }
  document.querySelectorAll('.sb-group').forEach(group => {
    const link = group.querySelector('.sb-link');
    const caret = group.querySelector('.sb-caret');
    if (!link || !caret) return;
    const key = group.dataset.group || (link.textContent || '').trim();
    // Khôi phục: mở nếu đã lưu (group active sẵn do trang hiện tại thì giữ nguyên)
    if (openSet.has(key)) group.classList.add('sb-group-active');
    const persist = () => {
      if (group.classList.contains('sb-group-active')) openSet.add(key); else openSet.delete(key);
      try { localStorage.setItem(KEY, JSON.stringify([...openSet])); } catch (e) {}
    };
    // Click caret → toggle, không navigate
    caret.addEventListener('click', (e) => {
      e.preventDefault(); e.stopPropagation();
      group.classList.toggle('sb-group-active');
      persist();
    });
    // Click link text → nếu đang đóng thì mở (không navigate); nếu đang mở thì navigate
    link.addEventListener('click', (e) => {
      if (e.target === caret) return;
      if (!group.classList.contains('sb-group-active')) {
        e.preventDefault();
        group.classList.add('sb-group-active');
        persist();
      }
    });
  });
})();

// ─── Mobile sidebar toggle ───
(() => {
  const toggle = document.getElementById('ph-mobile-menu');
  const sidebar = document.getElementById('sidebar');
  if (!toggle || !sidebar) return;
  toggle.addEventListener('click', () => {
    sidebar.classList.toggle('mobile-open');
    document.body.classList.toggle('sidebar-open');
  });
  // Click outside để close
  document.body.addEventListener('click', (e) => {
    if (!sidebar.classList.contains('mobile-open')) return;
    if (e.target === toggle || sidebar.contains(e.target)) return;
    sidebar.classList.remove('mobile-open');
    document.body.classList.remove('sidebar-open');
  });
})();

// ─── Global search ───
(() => {
  const input = document.getElementById('sb-search');
  const results = document.getElementById('sb-search-results');
  if (!input || !results) return;
  let timer = null;
  let focusedIdx = -1;

  // Phím tắt "/" để focus
  document.addEventListener('keydown', (e) => {
    if (e.key === '/' && !['INPUT', 'TEXTAREA'].includes(document.activeElement?.tagName)) {
      e.preventDefault();
      input.focus();
      input.select();
    }
    if (e.key === 'Escape' && document.activeElement === input) {
      input.blur();
      hideResults();
    }
  });

  function hideResults() {
    results.classList.add('hidden');
    focusedIdx = -1;
  }

  function escapeHtml(s) {
    return String(s || '').replace(/[&<>"']/g, c => ({
      '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
    }[c]));
  }

  async function search(q) {
    if (q.length < 2) { hideResults(); return; }
    results.classList.remove('hidden');
    results.innerHTML = '<div class="sb-search-loading">⏳ Đang tìm...</div>';
    try {
      const r = await fetch('/api/search?q=' + encodeURIComponent(q));
      const data = await r.json();
      const items = data.results || [];
      if (!items.length) {
        results.innerHTML = '<div class="sb-search-empty">Không tìm thấy</div>';
        return;
      }
      results.innerHTML = items.map((it, i) => `
        <a class="sb-search-item" href="${escapeHtml(it.href)}" data-idx="${i}">
          <div><span class="sb-search-icon">${escapeHtml(it.icon || '')}</span><span class="sb-search-title">${escapeHtml(it.title)}</span></div>
          ${it.snippet ? `<div class="sb-search-snippet">${escapeHtml(it.snippet)}</div>` : ''}
          ${it.tag ? `<span class="sb-search-tag">${escapeHtml(it.tag)}</span>` : ''}
        </a>
      `).join('');
    } catch (e) {
      results.innerHTML = '<div class="sb-search-empty">❌ Lỗi: ' + e.message + '</div>';
    }
  }

  input.addEventListener('input', () => {
    clearTimeout(timer);
    timer = setTimeout(() => search(input.value.trim()), 250);
  });
  input.addEventListener('focus', () => {
    if (input.value.trim().length >= 2) results.classList.remove('hidden');
  });
  document.body.addEventListener('click', (e) => {
    if (e.target === input || results.contains(e.target)) return;
    hideResults();
  });

  // Keyboard navigation
  input.addEventListener('keydown', (e) => {
    const items = results.querySelectorAll('.sb-search-item');
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      focusedIdx = Math.min(focusedIdx + 1, items.length - 1);
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      focusedIdx = Math.max(focusedIdx - 1, -1);
    } else if (e.key === 'Enter' && focusedIdx >= 0) {
      e.preventDefault();
      items[focusedIdx]?.click();
    }
    items.forEach((it, i) => it.classList.toggle('focused', i === focusedIdx));
  });
})();

// ─── Register Service Worker (PWA) ───
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('/static/sw.js').catch(() => {});
  });
}

// Floating Nox-1 chat widget
(() => {
  const fab = document.getElementById('nox-fab');
  const chat = document.getElementById('nox-chat');
  const closeBtn = document.getElementById('nox-chat-close');
  const form = document.getElementById('nox-chat-form');
  const input = document.getElementById('nox-chat-input');
  const log = document.getElementById('nox-chat-log');

  if (!fab) return;

  fab.addEventListener('click', () => {
    chat.classList.toggle('hidden');
    if (!chat.classList.contains('hidden')) input.focus();
  });
  closeBtn?.addEventListener('click', () => chat.classList.add('hidden'));

  function appendMsg(text, who) {
    const div = document.createElement('div');
    div.className = 'nox-msg ' + (who === 'me' ? 'nox-msg-me' : 'nox-msg-bot');
    div.textContent = text;
    log.appendChild(div);
    log.scrollTop = log.scrollHeight;
  }

  form?.addEventListener('submit', async (e) => {
    e.preventDefault();
    const msg = input.value.trim();
    if (!msg) return;
    appendMsg(msg, 'me');
    input.value = '';
    try {
      const r = await fetch('/api/widget-chat', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({message: msg}),
      });
      const j = await r.json();
      appendMsg(j.reply || '...', 'bot');
    } catch (err) {
      appendMsg('Lỗi kết nối: ' + err.message, 'bot');
    }
  });
})();

// ─── Toast notifications (thay alert() thô — non-blocking, đẹp) ───
(() => {
  function wrap() {
    let w = document.getElementById('toast-wrap');
    if (!w) { w = document.createElement('div'); w.id = 'toast-wrap'; document.body.appendChild(w); }
    return w;
  }
  function dismiss(el) { clearTimeout(el._t); el.classList.remove('show'); setTimeout(() => el.remove(), 260); }
  function toast(msg, type) {
    const m = String(msg == null ? '' : msg);
    let cls = type || '';
    if (!cls) {
      if (/✅|🎉|🚀|đã |xong|thành công/i.test(m)) cls = 'ok';
      else if (/❌|lỗi|fail|error|thất bại|vượt/i.test(m)) cls = 'err';
      else if (/⚠️|🚨|cảnh báo|gần|sắp/i.test(m)) cls = 'warn';
    }
    const el = document.createElement('div');
    el.className = 'toast ' + cls;
    const body = document.createElement('div'); body.textContent = m; body.style.flex = '1';
    const x = document.createElement('span'); x.className = 'toast-close'; x.textContent = '×';
    x.onclick = () => dismiss(el);
    el.appendChild(body); el.appendChild(x);
    wrap().appendChild(el);
    requestAnimationFrame(() => el.classList.add('show'));
    el._t = setTimeout(() => dismiss(el), Math.min(2600 + m.length * 28, 9000));
    return el;
  }
  window.toast = toast;
  // Ghi đè alert → toast. GIỮ confirm()/prompt() native (cần blocking để chặn thao tác).
  window.alert = (msg) => { toast(msg); };
})();

document.addEventListener('DOMContentLoaded', () => {
  // 1. Quick Stock Search Autocomplete
  const searchInput = document.getElementById('globalSearchInput');
  const searchDropdown = document.getElementById('searchDropdown');

  if (searchInput && searchDropdown) {
    let debounceTimer;

    searchInput.addEventListener('input', (e) => {
      clearTimeout(debounceTimer);
      const query = e.target.value.trim();

      if (query.length < 1) {
        searchDropdown.classList.remove('active');
        searchDropdown.innerHTML = '';
        return;
      }

      debounceTimer = setTimeout(async () => {
        try {
          const res = await fetch(`/api/search/?q=${encodeURIComponent(query)}`);
          const data = await res.json();

          if (data.results && data.results.length > 0) {
            searchDropdown.innerHTML = data.results.map(item => `
              <a href="/stock/${item.symbol}/" class="search-item">
                <div>
                  <div style="font-weight: 700; color: #fff;">${item.symbol}</div>
                  <div style="font-size: 0.8rem; color: #94a3b8;">${item.name} • ${item.sector}</div>
                </div>
                <div style="font-family: var(--font-mono); font-weight: 600; color: #38bdf8;">
                  ${item.price}
                </div>
              </a>
            `).join('');
            searchDropdown.classList.add('active');
          } else {
            searchDropdown.classList.remove('active');
          }
        } catch (err) {
          console.error('Search error:', err);
        }
      }, 250);
    });

    document.addEventListener('click', (e) => {
      if (!searchInput.contains(e.target) && !searchDropdown.contains(e.target)) {
        searchDropdown.classList.remove('active');
      }
    });
  }

  // 2. Interactive Run Daily Audit Trigger
  const runAuditBtn = document.getElementById('runAuditBtn');
  if (runAuditBtn) {
    runAuditBtn.addEventListener('click', async () => {
      const originalText = runAuditBtn.innerHTML;
      runAuditBtn.innerHTML = '⏳ Running 4:00 PM Verification Audit...';
      runAuditBtn.disabled = true;

      try {
        const csrftoken = getCookie('csrftoken') || '';
        const res = await fetch('/api/run-audit/', {
          method: 'POST',
          headers: {
            'X-CSRFToken': csrftoken,
            'Content-Type': 'application/json'
          }
        });
        const data = await res.json();

        if (data.success) {
          alert(`✅ Daily Audit Completed!\n\n• Targets Hit: ${data.result.targets_hit_today}\n• Stop Losses Hit: ${data.result.stop_losses_hit_today}\n• Current Win Rate: ${data.result.win_rate_pct}%\n\nPage will refresh to show updated records.`);
          window.location.reload();
        } else {
          alert('Audit executed.');
        }
      } catch (err) {
        console.error(err);
        alert('Audit completed. Refreshing...');
        window.location.reload();
      } finally {
        runAuditBtn.innerHTML = originalText;
        runAuditBtn.disabled = false;
      }
    });
  }
});

// Post-Mortem Diagnostic Modal Functions
function openPostMortemModal(title, category, diagnosis, rule, lesson) {
  const modal = document.getElementById('postMortemModal');
  if (!modal) return;

  document.getElementById('modalTitle').textContent = title;
  document.getElementById('modalCategory').textContent = category;
  document.getElementById('modalDiagnosis').textContent = diagnosis;
  document.getElementById('modalRule').textContent = rule || 'General Risk Protocol';
  document.getElementById('modalLesson').textContent = lesson;

  modal.classList.add('active');
}

function closePostMortemModal() {
  const modal = document.getElementById('postMortemModal');
  if (modal) modal.classList.remove('active');
}

// CSRF Token Helper
function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

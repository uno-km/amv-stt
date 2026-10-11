/**
 * Copyright (c) 2026 Uno Kim / AMEVA Foundation. All rights reserved.
 * SPDX-License-Identifier: Apache-2.0 OR Commercial-License
 */
/**
 * AMEVA Ecosystem - Unified Common Client Script (shared/common.js)
 * High-Clarity Enterprise Open-Source Standard (SSOT v3.1)
 * 
 * Features:
 * 1. Desktop Sidebar Edge Tab (< / >) Collapse Handle
 * 2. Mobile Responsive Top Header Hamburger Drawer (<= 960px)
 * 3. Collapsible Category Section Accordions
 * 4. Automatic Code Block Copy Tooltips
 * 5. Active Link Highlighting
 */

document.addEventListener('DOMContentLoaded', () => {
    const header = document.querySelector('header');
    const container = document.querySelector('.container');
    const sidebar = document.querySelector('.sidebar');

    if (!sidebar) return;

    // ── 1. Desktop Sidebar Edge Tab (< / > Toggle Handle) ─────────────────────
    let tabBtn = document.getElementById('sidebar-toggle-tab');
    if (!tabBtn) {
        tabBtn = document.createElement('div');
        tabBtn.id = 'sidebar-toggle-tab';
        tabBtn.className = 'sidebar-toggle-tab';
        tabBtn.setAttribute('title', '사이드바 접기/펼치기 (Toggle Sidebar)');
        tabBtn.setAttribute('aria-label', 'Toggle Sidebar');
        tabBtn.innerHTML = '‹';
        sidebar.appendChild(tabBtn);
    }

    function updateDesktopSidebar(collapsed) {
        if (collapsed) {
            sidebar.classList.add('desktop-collapsed');
            if (container) container.classList.add('sidebar-collapsed');
            tabBtn.classList.add('collapsed-tab');
            tabBtn.innerHTML = '›';
            document.body.appendChild(tabBtn); // Move to body for fixed left positioning
        } else {
            sidebar.classList.remove('desktop-collapsed');
            if (container) container.classList.remove('sidebar-collapsed');
            tabBtn.classList.remove('collapsed-tab');
            tabBtn.innerHTML = '‹';
            sidebar.appendChild(tabBtn); // Restore inside sidebar
        }
    }

    // Restore saved state
    const isSavedCollapsed = localStorage.getItem('ameva_desktop_sidebar_collapsed') === 'true';
    if (window.innerWidth > 960 && isSavedCollapsed) {
        updateDesktopSidebar(true);
    }

    tabBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        const willCollapse = !sidebar.classList.contains('desktop-collapsed');
        updateDesktopSidebar(willCollapse);
        localStorage.setItem('ameva_desktop_sidebar_collapsed', willCollapse ? 'true' : 'false');
    });

    // ── 2. Mobile Header Hamburger Button (Active <= 960px) ───────────────────
    if (header) {
        let toggleBtn = header.querySelector('.menu-toggle-btn');
        if (!toggleBtn) {
            toggleBtn = document.createElement('button');
            toggleBtn.className = 'menu-toggle-btn';
            toggleBtn.setAttribute('aria-label', 'Toggle Navigation Menu');
            toggleBtn.innerHTML = `
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round">
                    <line x1="3" y1="6" x2="21" y2="6"></line>
                    <line x1="3" y1="12" x2="21" y2="12"></line>
                    <line x1="3" y1="18" x2="21" y2="18"></line>
                </svg>
                <span class="menu-toggle-label">Menu</span>
            `;
            
            const controls = header.querySelector('.header-controls');
            if (controls) {
                controls.insertBefore(toggleBtn, controls.firstChild);
            } else {
                header.appendChild(toggleBtn);
            }
        }

        toggleBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            const isOpen = sidebar.classList.toggle('mobile-open');
            toggleBtn.classList.toggle('active', isOpen);
            toggleBtn.setAttribute('aria-expanded', isOpen ? 'true' : 'false');
        });

        // Close mobile drawer on link click
        sidebar.querySelectorAll('a').forEach(link => {
            link.addEventListener('click', () => {
                if (window.innerWidth <= 960) {
                    sidebar.classList.remove('mobile-open');
                    toggleBtn.classList.remove('active');
                }
            });
        });
    }

    // ── 3. Collapsible Sidebar Section Accordions ─────────────────────────────
    const headers = sidebar.querySelectorAll('h3');
    headers.forEach(h3 => {
        const ul = h3.nextElementSibling;
        if (!ul || ul.tagName !== 'UL') return;

        h3.classList.add('collapsible-header');

        if (!h3.querySelector('.accordion-icon')) {
            const icon = document.createElement('span');
            icon.className = 'accordion-icon';
            icon.textContent = '▾';
            h3.appendChild(icon);
        }

        h3.addEventListener('click', () => {
            const isCollapsed = ul.classList.toggle('collapsed');
            h3.classList.toggle('collapsed', isCollapsed);
            const icon = h3.querySelector('.accordion-icon');
            if (icon) {
                icon.textContent = isCollapsed ? '▸' : '▾';
            }
        });
    });

    // ── 4. Setup Copy Buttons on all <pre><code> blocks ───────────────────────
    document.querySelectorAll('pre').forEach((pre) => {
        if (pre.querySelector('.copy-code-btn')) return;

        const btn = document.createElement('button');
        btn.className = 'copy-code-btn';
        btn.setAttribute('aria-label', 'Copy code');
        btn.textContent = 'Copy';

        btn.addEventListener('click', async () => {
            const codeBlock = pre.querySelector('code') || pre;
            const textToCopy = codeBlock.innerText.trim();
            try {
                await navigator.clipboard.writeText(textToCopy);
                btn.textContent = 'Copied!';
                btn.style.backgroundColor = '#16a34a';
                btn.style.color = '#ffffff';

                setTimeout(() => {
                    btn.textContent = 'Copy';
                    btn.style.backgroundColor = '';
                    btn.style.color = '';
                }, 2000);
            } catch (err) {
                console.error('Failed to copy: ', err);
            }
        });

        pre.appendChild(btn);
    });

    // ── 5. Auto-highlight Active Link in Sidebar ───────────────────────────────
    const currentPath = window.location.pathname;
    document.querySelectorAll('.sidebar a').forEach(link => {
        const href = link.getAttribute('href');
        if (!href) return;
        
        if (href === currentPath || currentPath.endsWith(href) || (href === './' && currentPath.endsWith('/'))) {
            link.classList.add('active');
            const parentUl = link.closest('ul');
            if (parentUl) {
                parentUl.classList.remove('collapsed');
                const prevH3 = parentUl.previousElementSibling;
                if (prevH3 && prevH3.tagName === 'H3') {
                    prevH3.classList.remove('collapsed');
                    const icon = prevH3.querySelector('.accordion-icon');
                    if (icon) icon.textContent = '▾';
                }
            }
        }
    });
});

// ── 6. AmevaUI Global Enterprise SDK Suite (SSOT v3.2) ─────────────────────
window.AmevaUI = window.AmevaUI || {};

/**
 * Shows scoped loading overlay on target element with rugged spinner.
 * @param {HTMLElement|string} target - Container element or CSS selector
 * @param {string} message - Status text shown under spinner
 */
window.AmevaUI.showLoading = function(target, message = 'Loading Data...') {
  const el = typeof target === 'string' ? document.querySelector(target) : target;
  if (!el) return null;

  el.classList.add('ameva-loading-container');

  let overlay = el.querySelector(':scope > .ameva-loading-overlay');
  if (overlay) {
    const textEl = overlay.querySelector('.ameva-loading-text');
    if (textEl) textEl.textContent = message;
    overlay.style.opacity = '1';
    return overlay;
  }

  overlay = document.createElement('div');
  overlay.className = 'ameva-loading-overlay';
  overlay.innerHTML = `
    <div class="ameva-spinner"></div>
    <div class="ameva-loading-text">${message}</div>
  `;

  el.appendChild(overlay);
  return overlay;
};

/**
 * Hides scoped loading overlay with smooth fade-out.
 * @param {HTMLElement|string} target
 */
window.AmevaUI.hideLoading = function(target) {
  const el = typeof target === 'string' ? document.querySelector(target) : target;
  if (!el) return;

  const overlay = el.querySelector(':scope > .ameva-loading-overlay');
  if (overlay) {
    overlay.style.opacity = '0';
    setTimeout(() => {
      overlay.remove();
      el.classList.remove('ameva-loading-container');
    }, 200);
  }
};

/**
 * Executes async task while showing scoped loader on target element.
 * @param {HTMLElement|string} target
 * @param {Function} asyncFn
 * @param {string} message
 */
window.AmevaUI.withLoading = async function(target, asyncFn, message = 'Loading Data...') {
  window.AmevaUI.showLoading(target, message);
  try {
    return await asyncFn();
  } finally {
    window.AmevaUI.hideLoading(target);
  }
};

/**
 * 1-Line Fetch helper with automatic scoped loading overlay and JSON parsing.
 */
window.AmevaUI.fetchWithLoading = async function(target, url, options = {}, message = 'Fetching Telemetry...') {
  return await window.AmevaUI.withLoading(target, async () => {
    const res = await fetch(url, options);
    if (!res.ok) throw new Error(`HTTP ${res.status}: ${res.statusText}`);
    return await res.json();
  }, message);
};

/**
 * Smooth Count-Up Easing Animation (Cubic Ease-Out).
 * @param {HTMLElement|string} element
 * @param {number} targetValue
 * @param {number} duration - milliseconds (default: 750)
 * @param {string} suffix - e.g. "+", " TPS", " ms"
 * @param {string} prefix - e.g. "$", "#"
 */
window.AmevaUI.animateCount = function(element, targetValue, duration = 750, suffix = '', prefix = '') {
  const el = typeof element === 'string' ? document.querySelector(element) : element;
  if (!el) return;

  const startValue = parseInt(el.getAttribute('data-current-val') || '0', 10);
  const diff = targetValue - startValue;
  if (diff === 0 && el.textContent.trim()) return;

  const startTime = performance.now();

  function update(currentTime) {
    const elapsed = currentTime - startTime;
    const progress = Math.min(elapsed / duration, 1);
    const easeOut = 1 - Math.pow(1 - progress, 3);
    const currentVal = Math.round(startValue + diff * easeOut);

    el.textContent = prefix + currentVal.toLocaleString() + suffix;

    if (progress < 1) {
      requestAnimationFrame(update);
    } else {
      el.setAttribute('data-current-val', targetValue);
      el.textContent = prefix + targetValue.toLocaleString() + suffix;
    }
  }

  requestAnimationFrame(update);
};

/**
 * Declarative IntersectionObserver counter for any [data-count-to] elements on scroll.
 */
window.AmevaUI.initDeclarativeCounters = function() {
  const counters = document.querySelectorAll('[data-count-to]:not([data-counted])');
  if (!counters.length) return;

  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver((entries, obs) => {
      entries.forEach(entry => {
        if (entry.isIntersecting) {
          const el = entry.target;
          obs.unobserve(el);
          el.setAttribute('data-counted', 'true');
          const targetVal = parseFloat(el.getAttribute('data-count-to') || '0');
          const duration = parseInt(el.getAttribute('data-duration') || '750', 10);
          const suffix = el.getAttribute('data-suffix') || '';
          const prefix = el.getAttribute('data-prefix') || '';
          window.AmevaUI.animateCount(el, targetVal, duration, suffix, prefix);
        }
      });
    }, { threshold: 0.15 });

    counters.forEach(c => observer.observe(c));
  } else {
    counters.forEach(el => {
      const targetVal = parseFloat(el.getAttribute('data-count-to') || '0');
      const suffix = el.getAttribute('data-suffix') || '';
      const prefix = el.getAttribute('data-prefix') || '';
      el.textContent = prefix + targetVal.toLocaleString() + suffix;
    });
  }
};

// Auto-run declarative counters on DOM Ready
document.addEventListener('DOMContentLoaded', () => {
  window.AmevaUI.initDeclarativeCounters();
});

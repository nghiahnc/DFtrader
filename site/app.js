'use strict';
const $ = id => document.getElementById(id);
const number = value => value == null ? '—' : new Intl.NumberFormat('vi-VN', {maximumFractionDigits: 0}).format(value);
const pct = value => value == null ? '—' : `${value > 0 ? '+' : ''}${value.toFixed(1)}%`;
const formatTime = value => value ? new Intl.DateTimeFormat('vi-VN', {timeZone: 'Asia/Bangkok', day: '2-digit', month: '2-digit', year: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false}).format(new Date(value)) : 'Chưa có';
const escapeHtml = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const labels = {observe: 'Quan sát', watch: 'Đáng theo dõi', opportunity: 'Cơ hội sau phí', insufficient: 'Chưa đủ cơ sở', unavailable: 'Chưa có người bán'};
let report, runStatus, selected, visible = 15, range = 24;

function refreshHealth() {
  if (!report) return;
  const age = (Date.now() - Date.parse(report.source_updated_at)) / 3600000;
  const stale = age > report.thresholds.max_source_age_hours || age < -.1;
  const failed = !runStatus?.ok;
  $('freshness').textContent = failed ? 'Lượt quét gần nhất có lỗi' : stale ? 'Dữ liệu đã cũ' : 'Dữ liệu còn mới';
  $('freshness').className = `pill ${stale || failed ? 'bad' : 'good'}`;
  const notices = [];
  if (failed) notices.push(runStatus?.error || 'Không đọc được trạng thái lượt quét.');
  if (stale) notices.push('Báo cáo đang dùng dữ liệu cũ. Tạm ngừng đánh giá cơ hội mua.');
  if (!report.fee_confirmed) notices.push('Chưa xác nhận phí bán — chỉ theo dõi giá, chưa tính lãi ròng hoặc gửi cảnh báo mua.');
  if (!notices.length) notices.push('Đã tính phí theo cấu hình. Các cơ hội vẫn chưa được xác minh tốc độ bán thực tế.');
  $('system-banner').textContent = notices.join(' ');
  $('system-banner').className = `banner${stale || failed ? ' error' : ''}`;
  $('opportunities').textContent = stale || failed || !report.fee_confirmed ? '—' : number(report.items.filter(i => i.status === 'opportunity').length);
}

function renderList() {
  const query = $('search').value.trim().toLocaleLowerCase('vi');
  const status = $('status-filter').value;
  const sort = $('sort').value;
  const items = report.items.filter(i => i.name.toLocaleLowerCase('vi').includes(query) && (status === 'all' || (status === 'candidates' ? report.candidate_ids.includes(i.id) : i.status === status)));
  items.sort((a,b) => sort === 'name' ? a.name.localeCompare(b.name, 'vi') : sort === 'price' ? (a.price ?? Infinity) - (b.price ?? Infinity) : sort === 'discount' ? (b.discount_pct ?? -Infinity) - (a.discount_pct ?? -Infinity) : b.score - a.score);
  $('result-count').textContent = `${items.length} vật phẩm`;
  $('market-list').innerHTML = items.length ? '<div class="table-head" aria-hidden="true"><span>VẬT PHẨM / ĐANG RAO</span><span>GIÁ THẤP NHẤT</span><span>SO VỚI TV 24H</span><span>ĐÁNH GIÁ</span></div>' + items.slice(0, visible).map(item => `<button class="market-row" data-id="${escapeHtml(item.id)}" aria-pressed="${item.id === selected}" aria-label="Xem ${escapeHtml(item.name)}"><span><strong>${escapeHtml(item.name)}</strong><small>${item.price == null ? 'Không có người bán' : `${number(item.listed)} đang rao`}</small></span><span class="row-number">${number(item.price)}<small>Xu Tekniq</small></span><span class="row-discount ${item.discount_pct > 0 ? 'good' : item.discount_pct < 0 ? 'bad' : ''}">${pct(item.discount_pct == null ? null : -item.discount_pct)}</span><span class="row-signal ${item.status}">${labels[item.status]}</span></button>`).join('') : '<div class="empty">Không có vật phẩm phù hợp với bộ lọc.</div>';
  $('show-more').hidden = items.length <= visible;
  $('show-more').textContent = `Xem thêm (${items.length - Math.min(visible, items.length)})`;
}

function chart(item) {
  const points = item.history.filter(p => Date.parse(p.at) >= Date.parse(item.at) - range * 3600000);
  if (points.length < 2) return '<div class="empty">Chưa đủ dữ liệu để vẽ biểu đồ.</div>';
  const values = points.map(p => p.price), min = Math.min(...values), max = Math.max(...values);
  const span = max - min || Math.max(1, max * .02);
  const start = Date.parse(points[0].at), end = Date.parse(points.at(-1).at);
  const coords = points.map(p => [(Date.parse(p.at) - start) / (end - start || 1) * 334 + 3, 115 - (p.price - min) / span * 85]);
  const line = coords.map(p => p.join(',')).join(' ');
  const alt = `Giá thấp nhất ${number(min)}, cao nhất ${number(max)}; ${points.length} giờ quan sát trong ${range === 24 ? '24 giờ' : '7 ngày'}.`;
  return `<svg class="chart" viewBox="0 0 340 150" role="img" aria-label="${escapeHtml(alt)}"><title>${escapeHtml(alt)}</title><defs><linearGradient id="chart-fill" x1="0" y1="0" x2="0" y2="1"><stop offset="0%" stop-color="#244cbd" stop-opacity=".16"/><stop offset="100%" stop-color="#244cbd" stop-opacity="0"/></linearGradient></defs><path d="M3 30H337M3 72H337M3 115H337" stroke="#e1e6ee" stroke-dasharray="3 4"/><text x="4" y="18" fill="#59667a" font-size="9" font-family="monospace">${number(max)}</text><polygon points="3,138 ${line} 337,138" fill="url(#chart-fill)"/><polyline points="${line}" fill="none" stroke="#244cbd" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/><circle cx="${coords.at(-1)[0]}" cy="${coords.at(-1)[1]}" r="3.5" fill="#244cbd"/><text x="4" y="148" fill="#59667a" font-size="9" font-family="monospace">${number(min)}</text></svg><div class="chart-labels"><span>${formatTime(points[0].at)}</span><span>${formatTime(points.at(-1).at)}</span></div><details class="chart-table"><summary>Dữ liệu biểu đồ (${points.length} điểm)</summary><div style="max-height:190px;overflow:auto"><table style="width:100%;font-size:10px"><thead><tr><th>Thời điểm</th><th>Giá</th><th>Đang rao</th></tr></thead><tbody>${points.slice().reverse().map(p => `<tr><td>${formatTime(p.at)}</td><td>${number(p.price)}</td><td>${number(p.listed)}</td></tr>`).join('')}</tbody></table></div></details>`;
}

function renderDetail() {
  const item = report.items.find(i => i.id === selected);
  if (!item) return;
  let sourceUrl;
  try { const url = new URL(item.url); sourceUrl = url.protocol === 'https:' && url.hostname === 'dfloadout.gg' ? url.href : report.source_url; } catch { sourceUrl = report.source_url; }
  $('detail').innerHTML = `<div class="detail-head"><p class="eyebrow">PHÂN TÍCH VẬT PHẨM / ${escapeHtml(item.id)}</p><h2 id="detail-title">${escapeHtml(item.name)}</h2><span class="pill ${item.status === 'opportunity' || item.status === 'watch' ? 'good' : 'neutral'}">${labels[item.status]}</span><div class="detail-price">${number(item.price)}<span>Xu Tekniq / viên</span></div><p class="detail-meta">${number(item.listed)} đang rao · Nguồn: ${formatTime(item.at)} (UTC+7)</p></div><div class="chart-section"><div class="chart-heading"><span>Lịch sử giá rao</span><div class="range-buttons" role="group" aria-label="Khoảng thời gian biểu đồ"><button data-range="24" aria-pressed="${range === 24}">24 giờ</button><button data-range="168" aria-pressed="${range === 168}">7 ngày</button></div></div>${chart(item)}</div><dl class="detail-stats"><div><dt>Trung vị 24 giờ</dt><dd>${number(item.median24)}</dd></div><div><dt>Trung vị 7 ngày</dt><dd>${number(item.median7)}</dd></div><div><dt>Biến động 24 giờ</dt><dd>${item.volatility_pct == null ? '—' : item.volatility_pct.toFixed(1) + '%'}</dd></div><div><dt>Xu hướng gần đây</dt><dd>${pct(item.trend_pct)}</dd></div><div><dt>Giá hòa vốn sau phí</dt><dd>${number(item.breakeven)}</dd></div><div><dt>Giá mục tiêu tham khảo</dt><dd>${number(item.target)}</dd></div><div><dt>Biên dự kiến sau phí</dt><dd>${pct(item.net_margin_pct)}</dd></div><div><dt>Độ phủ 24 giờ / 7 ngày</dt><dd>${item.hours24}h / ${item.hours7}h</dd></div></dl><div class="reason-section"><h3>Cơ sở đánh giá</h3><ul>${item.reasons.map(reason => `<li>${escapeHtml(reason)}</li>`).join('')}</ul></div><a class="source-link" href="${escapeHtml(sourceUrl)}" target="_blank" rel="noopener noreferrer">Xem dữ liệu gốc trên DFLoadout ↗</a>`;
}

async function boot() {
  try {
    const [dataResponse, statusResponse] = await Promise.all([fetch('./data/report.json', {cache:'no-store'}), fetch('./data/status.json', {cache:'no-store'}).catch(() => null)]);
    if (!dataResponse.ok) throw new Error('report unavailable');
    report = await dataResponse.json();
    if (report.version !== 1 || !Array.isArray(report.items)) throw new Error('invalid report');
    runStatus = statusResponse?.ok ? await statusResponse.json().catch(() => null) : null;
    if (!report.items.length) throw new Error('no observations');
    $('analysis-time').textContent = `${formatTime(report.generated_at)} (UTC+7)`;
    $('source-time').textContent = `Nguồn cập nhật: ${formatTime(report.source_updated_at)}`;
    $('count').textContent = number(report.items.length);
    $('below').textContent = number(report.items.filter(i => i.discount_pct > 0 && i.hours24 >= report.thresholds.min_hours).length);
    const counts = report.items.filter(i => i.price != null).map(i => i.hours24).sort((a,b) => a-b);
    $('coverage').textContent = counts.length ? `${counts[Math.floor(counts.length / 2)]}h` : '—';
    $('fee-caption').textContent = report.fee_confirmed ? `Phí bán ${report.fee.sale_rate * 100}%, phí rao ${report.fee.listing_rate * 100}%` : 'Chờ xác nhận cách tính phí';
    $('method-thresholds').textContent = `Ứng viên cần giảm ít nhất ${report.thresholds.min_discount_pct}% so với trung vị 24 giờ, biến động không quá ${report.thresholds.max_volatility_pct}%, xu hướng gần đây không giảm quá 3%. Cơ hội sau phí cần biên tối thiểu ${report.thresholds.min_net_margin_pct}% và đủ lịch sử 7 ngày.`;
    selected = report.candidate_ids[0] || report.items[0]?.id;
    refreshHealth(); renderList(); renderDetail();
    setInterval(refreshHealth, 60000);
    for (const id of ['search','status-filter','sort']) $(id).addEventListener(id === 'search' ? 'input' : 'change', () => { visible = 15; renderList(); });
    $('show-more').addEventListener('click', () => { visible += 20; renderList(); });
    $('market-list').addEventListener('click', event => {
      const button = event.target.closest('[data-id]');
      if (!button) return;
      selected = button.dataset.id; renderList(); renderDetail();
      $('market-list').querySelector(`[data-id="${selected}"]`)?.focus({preventScroll:true});
      if (matchMedia('(max-width:800px)').matches) $('detail').scrollIntoView({behavior: matchMedia('(prefers-reduced-motion:reduce)').matches ? 'instant' : 'smooth', block:'start'});
    });
    $('detail').addEventListener('click', event => {
      const button = event.target.closest('[data-range]');
      if (!button) return;
      range = Number(button.dataset.range); renderDetail();
      $('detail').querySelector(`[data-range="${range}"]`).focus({preventScroll:true});
    });
  } catch {
    $('system-banner').textContent = 'Chưa tải được báo cáo hợp lệ. Kiểm tra kết nối rồi tải lại trang.';
    $('system-banner').className = 'banner error';
    $('freshness').textContent = 'Chưa có dữ liệu';
    $('analysis-time').textContent = 'Chưa có báo cáo';
    $('market-list').innerHTML = '<div class="empty">Chưa có dữ liệu để hiển thị. Không tạo tín hiệu từ dữ liệu thiếu.</div>';
  }
}
boot();

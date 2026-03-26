async function fetchDashboard() {
  try {
    const res = await fetch('/api/dashboard');
    if (!res.ok) throw new Error('fetch error');
    return await res.json();
  } catch (e) {
    console.error(e);
    return null;
  }
}

function renderKPIs(data) {
  document.getElementById('kpi-not-sent').textContent = data.kpis.not_sent || 0;
  document.getElementById('kpi-sent').textContent = data.kpis.sent || 0;
  document.getElementById('kpi-to-send').textContent = data.kpis.to_send || 0;
  document.getElementById('kpi-new').textContent = data.kpis.new_version || 0;
}

function renderLineChart(ctx, series) {
  const labels = series.labels;
  const finished = series.finished;
  const notfinished = series.not_finished;
  new Chart(ctx, {
    type: 'line',
    data: {
      labels,
      datasets: [
        { label: 'Taches finies', data: finished, borderColor: '#2e7d32', backgroundColor: 'transparent' },
        { label: 'Taches non finies', data: notfinished, borderColor: '#ef6c00', backgroundColor: 'transparent' }
      ]
    },
    options: { responsive: true }
  });
}

function renderPie(ctx, pieData) {
  new Chart(ctx, {
    type: 'pie',
    data: {
      labels: pieData.labels,
      datasets: [{ data: pieData.values, backgroundColor: ['#b24592','#ef8e3a','#1b5e20','#03a9f4'] }]
    },
    options: { responsive: true }
  });
}

(async function(){
  const data = await fetchDashboard();
  if (!data) return;
  renderKPIs(data);
  const lineCtx = document.getElementById('lineChart').getContext('2d');
  renderLineChart(lineCtx, data.series);
  const pieCtx = document.getElementById('pieChart').getContext('2d');
  renderPie(pieCtx, data.priority);
})();

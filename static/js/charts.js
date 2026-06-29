async function initChart() {
    const response = await fetch('/api/stats');
    const stats = await response.json();
    
    // stats is a list of {name, teaching, research, admin}
    const facultyNames = stats.map(s => s.name);
    
    // We'll create a pie chart showing the aggregate distribution across all faculty
    const totalTeaching = stats.reduce((sum, s) => sum + s.spending_time_teaching, 0);
    const totalResearch = stats.reduce((sum, s) => sum + s.spending_time_research, 0);
    const totalAdmin = stats.reduce((sum, s) => sum + s.spending_time_admin, 0);

    const ctx = document.getElementById('comparisonChart').getContext('2d');
    new Chart(ctx, {
        type: 'pie',
        data: {
            labels: ['Teaching', 'Research', 'Admin'],
            datasets: [
                {
                    data: [totalTeaching, totalResearch, totalAdmin],
                    backgroundColor: ['#6366f1', '#10b981', '#f59e0b'],
                    borderColor: 'rgba(255, 255, 255, 0.1)',
                    borderWidth: 2
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { color: '#f8fafc', padding: 20 }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const label = context.label || '';
                            const value = context.raw || 0;
                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                            const percentage = Math.round((value / total) * 100);
                            return `${label}: ${value} hrs (${percentage}%)`;
                        }
                    }
                }
            }
        }
    });
}

initChart();

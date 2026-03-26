document.addEventListener('DOMContentLoaded', function() {
    // État global
    let activityChart = null;
    let rolesChart = null;
    let refreshInterval = null;
    let isLoading = false;
    
    // Éléments DOM
    const globalLoading = document.getElementById('global-loading');
    const lastUpdateEl = document.getElementById('last-update');
    
    // Couleurs personnalisées
    const COLORS = {
        primary: '#3498db',
        success: '#27ae60',
        warning: '#e67e22',
        danger: '#e74c3c',
        purple: '#9b59b6',
        teal: '#1abc9c'
    };
    
    // Formateurs
    const formatters = {
        date: new Intl.DateTimeFormat('fr-FR', {
            day: '2-digit',
            month: '2-digit',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        }),
        number: new Intl.NumberFormat('fr-FR', {
            minimumFractionDigits: 0,
            maximumFractionDigits: 0
        })
    };
    
    // Gestionnaire de cache
    const cache = {
        data: null,
        timestamp: null,
        ttl: 30000, // 30 secondes
        
        set(data) {
            this.data = data;
            this.timestamp = Date.now();
        },
        
        get() {
            if (!this.data || !this.timestamp) return null;
            if (Date.now() - this.timestamp > this.ttl) return null;
            return this.data;
        },
        
        clear() {
            this.data = null;
            this.timestamp = null;
        }
    };
    
    // Afficher/masquer loading
    function showLoading() {
        if (!isLoading) {
            isLoading = true;
            if (globalLoading) globalLoading.style.display = 'block';
        }
    }
    
    function hideLoading() {
        if (isLoading) {
            isLoading = false;
            if (globalLoading) globalLoading.style.display = 'none';
        }
    }
    
    // Mise à jour des statistiques
    async function loadStats(forceRefresh = false) {
        // Vérifier le cache
        if (!forceRefresh) {
            const cachedData = cache.get();
            if (cachedData) {
                updateUI(cachedData);
                return;
            }
        }
        
        showLoading();
        
        try {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 10000); // Timeout 10s
            
            const response = await fetch('/api/admin/summary', {
                signal: controller.signal,
                headers: {
                    'Cache-Control': 'no-cache',
                    'Pragma': 'no-cache'
                }
            });
            
            clearTimeout(timeoutId);
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const data = await response.json();
            
            // Valider les données
            if (!data || typeof data !== 'object') {
                throw new Error('Format de données invalide');
            }
            
            // Mettre en cache
            cache.set(data);
            
            // Mettre à jour l'interface
            updateUI(data);
            
        } catch (error) {
            console.error('Erreur chargement stats:', error);
            
            if (error.name === 'AbortError') {
                showToast('Délai d\'attente dépassé', 'warning');
            } else {
                showToast('Erreur de chargement des données', 'danger');
            }
            
            // Afficher des valeurs par défaut
            updateUIWithDefaultValues();
            
        } finally {
            hideLoading();
        }
    }
    
    // Mise à jour de l'interface
    function updateUI(data) {
        // Éléments KPI
        const elements = {
          'total-users': data.total_users,
          // main value for active-users shows currently connected users
          'active-users': data.connected_now !== undefined ? data.connected_now : data.active_users,
          'connexions-today': data.connexions_today,
          'total-dossiers': data.total_dossiers
        };
        
        for (const [id, value] of Object.entries(elements)) {
            const el = document.getElementById(id);
            if (el) {
                // Animation de changement
                if (el.textContent !== String(value)) {
                    el.style.transition = 'background-color 0.3s';
                    el.style.backgroundColor = 'rgba(52,152,219,0.1)';
                    setTimeout(() => {
                        el.style.backgroundColor = '';
                    }, 300);
                }
                el.textContent = formatters.number.format(value || 0);
            }
        }
        
        // Graphique d'activité
        if (data.activity) {
            updateActivityChart(data.activity);
        }
        
        // Graphique des rôles
        if (data.roles) {
            updateRolesChart(data.roles);
        }
        
        // Dernière mise à jour
        if (lastUpdateEl) {
            const now = new Date();
            lastUpdateEl.textContent = formatters.date.format(now);
            lastUpdateEl.setAttribute('datetime', now.toISOString());
        }

        // Update active-users subtext with 30-day active users when available
        try {
          const subEl = document.getElementById('active-users-sub');
          if (subEl) {
            const active30 = data.active_users_30d !== undefined && data.active_users_30d !== null ? data.active_users_30d : 0;
            subEl.innerHTML = `<i class="fas fa-history"></i> ${formatters.number.format(active30)} actifs (30j)`;
          }
        } catch (e) { console.error('Erreur mise à jour sous-texte active-users', e); }
    }
    
    // Valeurs par défaut en cas d'erreur
    function updateUIWithDefaultValues() {
        const defaultValues = {
            'total-users': '0',
            'active-users': '0',
            'connexions-today': '0',
            'total-dossiers': '0'
        };
        
        for (const [id, value] of Object.entries(defaultValues)) {
            const el = document.getElementById(id);
            if (el) el.textContent = value;
        }
        
        if (lastUpdateEl) {
            lastUpdateEl.textContent = formatters.date.format(new Date());
        }
    }
    
    // Graphique d'activité
    function updateActivityChart(activityData) {
        const ctx = document.getElementById('activityChart')?.getContext('2d');
        if (!ctx) return;
        
        // Données par défaut si non fournies
        const labels = activityData?.labels || ['Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam', 'Dim'];
        const data = activityData?.data || [0, 0, 0, 0, 0, 0, 0];
        
        if (activityChart) {
            activityChart.destroy();
        }
        
        activityChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [{
                    label: 'Connexions',
                    data: data,
                    borderColor: COLORS.primary,
                    backgroundColor: 'rgba(52,152,219,0.1)',
                    borderWidth: 2,
                    pointBackgroundColor: COLORS.primary,
                    pointBorderColor: '#fff',
                    pointBorderWidth: 2,
                    pointRadius: 4,
                    pointHoverRadius: 6,
                    tension: 0.3,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: {
                        display: false
                    },
                    tooltip: {
                        backgroundColor: 'white',
                        titleColor: '#2c3e50',
                        bodyColor: '#666',
                        borderColor: COLORS.primary,
                        borderWidth: 1,
                        padding: 12,
                        callbacks: {
                            label: (context) => {
                                return `${context.parsed.y} connexion${context.parsed.y > 1 ? 's' : ''}`;
                            }
                        }
                    }
                },
                scales: {
                    y: {
                        beginAtZero: true,
                        grid: {
                            color: 'rgba(0,0,0,0.05)'
                        },
                        ticks: {
                            stepSize: 1,
                            callback: (value) => formatters.number.format(value)
                        }
                    },
                    x: {
                        grid: {
                            display: false
                        }
                    }
                }
            }
        });
    }
    
    // Graphique des rôles
    function updateRolesChart(rolesData) {
        const ctx = document.getElementById('rolesChart')?.getContext('2d');
        if (!ctx) return;
        
        // Données par défaut
        const labels = rolesData?.labels || ['Administrateurs', 'Gestionnaires', 'Commerciaux', 'Clients', 'Visiteurs'];
        const data = rolesData?.data || [0, 0, 0, 0, 0];
        
        if (rolesChart) {
            rolesChart.destroy();
        }
        
        const backgroundColors = [
            COLORS.danger,
            COLORS.warning,
            COLORS.success,
            COLORS.primary,
            COLORS.purple,
            COLORS.teal
        ];
        
        rolesChart = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{
                    data: data,
                    backgroundColor: backgroundColors.slice(0, data.length),
                    borderWidth: 3,
                    borderColor: 'white',
                    hoverOffset: 10
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                cutout: '65%',
                plugins: {
                    legend: {
                        position: 'bottom',
                        labels: {
                            boxWidth: 12,
                            padding: 15,
                            font: {
                                size: 11
                            }
                        }
                    },
                    tooltip: {
                        backgroundColor: 'white',
                        titleColor: '#2c3e50',
                        bodyColor: '#666',
                        borderColor: COLORS.primary,
                        borderWidth: 1,
                        padding: 12,
                        callbacks: {
                            label: (context) => {
                                const value = context.parsed;
                                const total = context.dataset.data.reduce((a, b) => a + b, 0);
                                const percentage = total > 0 ? ((value / total) * 100).toFixed(1) : 0;
                                return `${context.label}: ${value} (${percentage}%)`;
                            }
                        }
                    }
                }
            }
        });
        
        // Mettre à jour la légende personnalisée
        updateRolesLegend(labels, data, backgroundColors);
    }
    
    // Légende personnalisée pour les rôles
    function updateRolesLegend(labels, data, colors) {
        const legendEl = document.getElementById('roles-legend');
        if (!legendEl) return;
        
        const total = data.reduce((a, b) => a + b, 0);
        
        legendEl.innerHTML = labels.map((label, index) => {
            const value = data[index];
            const percentage = total > 0 ? ((value / total) * 100).toFixed(1) : 0;
            return `
                <div style="display: flex; align-items: center; gap: 8px;">
                    <span style="display: inline-block; width: 12px; height: 12px; border-radius: 3px; background: ${colors[index]};"></span>
                    <span style="font-size: 0.85rem; color: #666;">
                        ${label}: <strong>${formatters.number.format(value)}</strong> (${percentage}%)
                    </span>
                </div>
            `;
        }).join('');
    }
    
    // Notifications toast
    function showToast(message, type = 'info') {
        // Créer l'élément toast
        const toast = document.createElement('div');
        toast.style.cssText = `
            position: fixed;
            bottom: 20px;
            left: 20px;
            background: white;
            padding: 12px 24px;
            border-radius: 8px;
            box-shadow: 0 5px 20px rgba(0,0,0,0.15);
            border-left: 4px solid ${COLORS[type] || COLORS.info};
            z-index: 10000;
            animation: slideIn 0.3s ease;
            font-size: 0.95rem;
            display: flex;
            align-items: center;
            gap: 10px;
        `;
        
        // Icône selon le type
        const icon = document.createElement('i');
        icon.className = `fas fa-${type === 'success' ? 'check-circle' : 
                               type === 'danger' ? 'exclamation-circle' : 
                               type === 'warning' ? 'exclamation-triangle' : 'info-circle'}`;
        icon.style.color = COLORS[type] || COLORS.info;
        
        toast.appendChild(icon);
        toast.appendChild(document.createTextNode(message));
        
        document.body.appendChild(toast);
        
        // Animation d'entrée
        const style = document.createElement('style');
        style.textContent = `
            @keyframes slideIn {
                from { transform: translateX(-100%); opacity: 0; }
                to { transform: translateX(0); opacity: 1; }
            }
        `;
        document.head.appendChild(style);
        
        // Supprimer après 5 secondes
        setTimeout(() => {
            toast.style.animation = 'slideIn 0.3s ease reverse';
            setTimeout(() => toast.remove(), 300);
        }, 5000);
    }
    
    // Rafraîchissement manuel
    function refreshData() {
        cache.clear();
        loadStats(true);
        showToast('Données mises à jour', 'success');
    }
    
    // Gestion des KPI cards au clic
    function initKPICards() {
        document.querySelectorAll('.kpi-card').forEach(card => {
            card.addEventListener('click', function() {
                // Retirer la classe active de toutes les cartes
                document.querySelectorAll('.kpi-card').forEach(c => c.classList.remove('active'));
                // Ajouter la classe active à la carte cliquée
                this.classList.add('active');
                
                const key = this.getAttribute('data-key');
                showToast(`Affichage des détails: ${key}`, 'info');
                
                // Ici vous pouvez ajouter la redirection vers la liste détaillée
                // window.location.href = `/dashboard/admin/list?type=${key}`;
            });
        });
    }
    
    // Initialisation
    function init() {
        // Charger les données
        loadStats();
        
        // Initialiser les KPI cards
        initKPICards();
        
        // Rafraîchissement automatique toutes les 30 secondes
        refreshInterval = setInterval(() => loadStats(), 30000);
        
        // Gestionnaire de visibilité de la page
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                clearInterval(refreshInterval);
            } else {
                loadStats(true);
                refreshInterval = setInterval(() => loadStats(), 30000);
            }
        });
        
        // Gestionnaire de rafraîchissement manuel (Ctrl+R ou Cmd+R)
        window.addEventListener('keydown', (e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === 'r') {
                e.preventDefault();
                refreshData();
            }
        });
        
        // Nettoyage à la décharge
        window.addEventListener('beforeunload', () => {
            clearInterval(refreshInterval);
        });
        
        // Gestionnaire pour le bouton de rafraîchissement (si présent)
        const refreshBtn = document.getElementById('refresh-data');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', refreshData);
        }
    }
    
    // Démarrer
    init();
});

// Gestionnaire d'erreur global pour les promesses non gérées
window.addEventListener('unhandledrejection', function(event) {
    console.error('Erreur non gérée:', event.reason);
    // Empêcher l'affichage dans la console des erreurs de fetch normales
    if (event.reason?.name === 'AbortError') {
        event.preventDefault();
    }
});


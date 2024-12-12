document.addEventListener('DOMContentLoaded', function() {
    const uploadForm = document.getElementById('uploadForm');
    const loading = document.getElementById('loading');
    const error = document.getElementById('error');
    const results = document.getElementById('results');
    const errorMessage = document.getElementById('errorMessage');

    // Form submission handler
    uploadForm.addEventListener('submit', async function(e) {
        e.preventDefault();
        
        const formData = new FormData();
        const fileInput = document.getElementById('jsonFile');
        
        if (!fileInput.files[0]) {
            showError('Please select a file to upload');
            return;
        }
        
        formData.append('file', fileInput.files[0]);

        try {
            showLoading();
            hideError();
            hideResults();

            const response = await fetch('/analyze', {
                method: 'POST',
                body: formData
            });

            if (!response.ok) {
                throw new Error('Analysis failed');
            }

            const data = await response.json();
            displayResults(data);
        } catch (err) {
            showError(err.message);
        } finally {
            hideLoading();
        }
    });

    // Main display function
    function displayResults(data) {
        showResults();
        
        // Calculate averages and totals
        const serverCount = data.servers.length;
        const averageComplexity = data.servers.reduce((sum, server) => 
            sum + parseFloat(server.complexity.percentage), 0) / serverCount;
        
        // Update overview section
        document.getElementById('totalServers').textContent = serverCount;
        document.getElementById('avgComplexity').textContent = formatNumber(averageComplexity / 100 * 15);
        
        // Process costs and display sections
        const costData = processServerCosts(data.servers);
        displayServerAnalysis(data.servers, costData);
        displayCostAnalysis(data.servers, costData);
        displayMigrationRoadmap(data.roadmap);
        
        // Update overview total cost
        document.getElementById('totalCost').textContent = formatINR(costData.totalMigrationCost);
    }

    // Cost processing function
    function processServerCosts(servers) {
        let totalMigrationCost = 0;
        let monthlyCloudCost = 0;
        let currentCosts = 0;
        let serverCosts = {};

        servers.forEach(server => {
            const costs = calculateServerCosts(server);
            serverCosts[server.serverData.serverId] = costs;
            
            totalMigrationCost += costs.migrationCost;
            monthlyCloudCost += costs.projectedMonthlyCost;
            currentCosts += costs.currentMonthlyCost;
        });

        const monthlySavings = currentCosts - monthlyCloudCost;
        const roiMonths = monthlySavings > 0 ? Math.ceil(totalMigrationCost / monthlySavings) : 0;

        return {
            totalMigrationCost,
            monthlyCloudCost,
            currentCosts,
            monthlySavings,
            roiMonths,
            serverCosts
        };
    }

    // Server cost calculation
    function calculateServerCosts(server) {
        const baselineCost = getBaselineMigrationCost(server.migrationStrategy.strategy);
        const complexityMultiplier = getComplexityMultiplier(server.complexity.level);
        
        // Calculate monthly cloud costs
        const computeCost = calculateComputeCost(server.serverData.metrics);
        const storageCost = calculateStorageCost(server.serverData.metrics);
        const networkCost = calculateNetworkCost(server.serverData.networkUtilization);
        
        const projectedMonthlyCost = computeCost + storageCost + networkCost;
        const currentMonthlyCost = projectedMonthlyCost * 1.4; // Assuming 40% higher on-premises
        const migrationCost = baselineCost * complexityMultiplier;
        
        return {
            projectedMonthlyCost,
            currentMonthlyCost,
            migrationCost,
            savings: currentMonthlyCost - projectedMonthlyCost
        };
    }

    // Cost calculation helpers
    function calculateComputeCost(metrics) {
        // Cost per core per month in INR
        const costPerCore = 3000; // ₹3,000 per core
        const utilizationFactor = metrics.cpu.utilization / 100;
        return metrics.cpu.cores * costPerCore * utilizationFactor;
    }

    function calculateStorageCost(metrics) {
        // Storage cost per GB per month in INR
        const costPerGB = 100; // ₹100 per GB
        const storageGB = metrics.storage.total / (1024 * 1024); // Convert KB to GB
        return storageGB * costPerGB;
    }

    function calculateNetworkCost(networkUtilization) {
        // Network cost per GB of bandwidth per month in INR
        const costPerGBBandwidth = 50; // ₹50 per GB bandwidth
        return (networkUtilization.bandwidth * networkUtilization.averageUsage / 100) * costPerGBBandwidth;
    }

    function getBaselineMigrationCost(strategy) {
        const costs = {
            'Rehost': 500000,     // ₹5 lakhs
            'Replatform': 1000000, // ₹10 lakhs
            'Refactor': 2000000    // ₹20 lakhs
        };
        return costs[strategy] || costs.Rehost;
    }

    function getComplexityMultiplier(level) {
        const multipliers = {
            'High': 1.5,
            'Medium': 1.2,
            'Low': 1.0
        };
        return multipliers[level] || 1.0;
    }

    // Display functions
    function displayServerAnalysis(servers, costData) {
        const serverAnalysis = document.getElementById('serverAnalysis');
        serverAnalysis.innerHTML = servers.map(server => {
            const costs = costData.serverCosts[server.serverData.serverId];
            
            return `
                <div class="bg-white border rounded-lg p-6 hover:shadow-lg transition-duration-300">
                    <div class="flex justify-between items-start">
                        <div>
                            <h3 class="text-xl font-semibold text-gray-900">${server.serverData.serverName}</h3>
                            <p class="text-sm text-gray-500">ID: ${server.serverData.serverId}</p>
                        </div>
                        <span class="px-3 py-1 rounded-full text-sm font-medium ${getComplexityClass(server.complexity.level)}">
                            ${server.complexity.level} Complexity
                        </span>
                    </div>

                    <div class="mt-6 grid grid-cols-1 md:grid-cols-2 gap-6">
                        <div class="space-y-4">
                            <div>
                                <h4 class="text-sm font-medium text-gray-500">Resources</h4>
                                <ul class="mt-2 space-y-2">
                                    <li class="flex justify-between">
                                        <span class="text-gray-600">CPU:</span>
                                        <span>${server.serverData.metrics.cpu.cores} cores (${server.serverData.metrics.cpu.utilization}% utilized)</span>
                                    </li>
                                    <li class="flex justify-between">
                                        <span class="text-gray-600">Memory:</span>
                                        <span>${formatBytes(server.serverData.metrics.memory.total)} (${formatBytes(server.serverData.metrics.memory.used)} used)</span>
                                    </li>
                                    <li class="flex justify-between">
                                        <span class="text-gray-600">Storage:</span>
                                        <span>${formatBytes(server.serverData.metrics.storage.total)} (${formatBytes(server.serverData.metrics.storage.used)} used)</span>
                                    </li>
                                </ul>
                            </div>

                            <div>
                                <h4 class="text-sm font-medium text-gray-500">Applications</h4>
                                <div class="mt-2 flex flex-wrap gap-2">
                                    ${server.serverData.applications.map(app => `
                                        <span class="px-2 py-1 bg-gray-100 text-gray-700 rounded text-sm">${app}</span>
                                    `).join('')}
                                </div>
                            </div>
                        </div>

                        <div class="space-y-4">
                            <div>
                                <h4 class="text-sm font-medium text-gray-500">Migration Strategy</h4>
                                <div class="mt-2">
                                    <p class="text-lg font-medium text-blue-600">${server.migrationStrategy.strategy}</p>
                                    <p class="mt-1 text-sm text-gray-600">${server.migrationStrategy.description}</p>
                                </div>
                            </div>

                            <div>
                                <h4 class="text-sm font-medium text-gray-500">Recommended AWS Services</h4>
                                <div class="mt-2 flex flex-wrap gap-2">
                                    ${server.migrationStrategy.aws_services.map(service => `
                                        <span class="px-2 py-1 bg-blue-100 text-blue-800 rounded text-sm">${service}</span>
                                    `).join('')}
                                </div>
                            </div>

                            <div>
                                <h4 class="text-sm font-medium text-gray-500">Cost Analysis</h4>
                                <div class="mt-2 grid grid-cols-2 gap-4">
                                    <div>
                                        <p class="text-sm text-gray-600">Current Monthly</p>
                                        <p class="text-lg font-semibold text-gray-900">${formatINR(costs.currentMonthlyCost)}</p>
                                    </div>
                                    <div>
                                        <p class="text-sm text-gray-600">Projected Monthly</p>
                                        <p class="text-lg font-semibold text-green-600">${formatINR(costs.projectedMonthlyCost)}</p>
                                    </div>
                                    <div>
                                        <p class="text-sm text-gray-600">Migration Cost</p>
                                        <p class="text-lg font-semibold text-blue-600">${formatINR(costs.migrationCost)}</p>
                                    </div>
                                    <div>
                                        <p class="text-sm text-gray-600">Monthly Savings</p>
                                        <p class="text-lg font-semibold text-purple-600">${formatINR(costs.currentMonthlyCost - costs.projectedMonthlyCost)}</p>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        }).join('');
    }

    function displayCostAnalysis(servers, costData) {
        // Update summary metrics
        document.getElementById('monthlyCloudCost').textContent = formatINR(costData.monthlyCloudCost);
        document.getElementById('totalMigrationCost').textContent = formatINR(costData.totalMigrationCost);
        document.getElementById('roiTimeline').textContent = `${costData.roiMonths} months`;
        
        // Create cost comparison chart
        createCostChart(servers, costData);
        
        // Update cost summary
        const annualSavings = costData.monthlySavings * 12;
        const threeYearSavings = (costData.monthlySavings * 36) - costData.totalMigrationCost;
        const costReduction = ((costData.currentCosts - costData.monthlyCloudCost) / costData.currentCosts) * 100;

        document.getElementById('costSummary').innerHTML = `
            <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div class="bg-blue-50 p-4 rounded-lg">
                    <h4 class="text-sm font-medium text-blue-800">Annual Savings</h4>
                    <p class="text-xl font-bold text-blue-600">${formatINR(annualSavings)}</p>
                </div>
                <div class="bg-green-50 p-4 rounded-lg">
                    <h4 class="text-sm font-medium text-green-800">3-Year Savings</h4>
                    <p class="text-xl font-bold text-green-600">${formatINR(threeYearSavings)}</p>
                </div>
                <div class="bg-purple-50 p-4 rounded-lg">
                    <h4 class="text-sm font-medium text-purple-800">Cost Reduction</h4>
                    <p class="text-xl font-bold text-purple-600">${formatNumber(costReduction)}%</p>
                </div>
                <div class="bg-yellow-50 p-4 rounded-lg">
                    <h4 class="text-sm font-medium text-yellow-800">Break-even Point</h4>
                    <p class="text-xl font-bold text-yellow-600">${costData.roiMonths} months</p>
                </div>
            </div>
        `;
    }

    function createCostChart(servers, costData) {
        const chartData = servers.map(server => {
            const costs = costData.serverCosts[server.serverData.serverId];
            return {
                name: server.serverData.serverName,
                'Current Monthly': costs.currentMonthlyCost,
                'Projected Monthly': costs.projectedMonthlyCost,
                'Migration Cost': costs.migrationCost
            };
        });

        const traces = [
            {
                x: chartData.map(d => d.name),
                y: chartData.map(d => d['Current Monthly']),
                name: 'Current Monthly',
                type: 'bar',
                marker: { color: '#60A5FA' }
            },
            {
                x: chartData.map(d => d.name),
                y: chartData.map(d => d['Projected Monthly']),
                name: 'Projected Monthly',
                type: 'bar',
                marker: { color: '#34D399' }
            },
            {
                x: chartData.map(d => d.name),
                y: chartData.map(d => d['Migration Cost']),
                name: 'Migration Cost',
                type: 'bar',
                marker: { color: '#F87171' }
            }
        ];

        const layout = {
            title: 'Cost Comparison by Server',
            barmode: 'group',
            yaxis: {
                title: 'Cost (₹)',
                tickformat: '.2s',
                tickprefix: '₹'
            },
            legend: {
                orientation: 'h',
                y: -0.2
            },
            margin: { t: 40, b: 100 }
        };

        Plotly.newPlot('costChart', traces, layout);
    }

    // Utility functions
    function formatINR(amount) {
        return new Intl.NumberFormat('en-IN', {
            style: 'currency',
            currency: 'INR',
            maximumFractionDigits: 0
        }).format(amount);
    }

    function formatNumber(num) {
        return new Intl.NumberFormat('en-IN', {
            maximumFractionDigits: 2
        }).format(num);
    }

    // Continue formatBytes function
    function formatBytes(bytes) {
        const units = ['B', 'KB', 'MB', 'GB', 'TB'];
        let unitIndex = 0;
        let size = bytes;

        while (size >= 1024 && unitIndex < units.length - 1) {
            size /= 1024;
            unitIndex++;
        }

        return `${size.toFixed(1)} ${units[unitIndex]}`;
    }

    function getComplexityClass(level) {
        const classes = {
            'High': 'bg-red-100 text-red-800',
            'Medium': 'bg-yellow-100 text-yellow-800',
            'Low': 'bg-green-100 text-green-800'
        };
        return classes[level] || 'bg-gray-100 text-gray-800';
    }

    function getRiskClass(level) {
        const classes = {
            'High': 'text-red-600 font-medium',
            'Medium': 'text-yellow-600 font-medium',
            'Low': 'text-green-600 font-medium'
        };
        return classes[level] || 'text-gray-600';
    }

    // Display functions for migration roadmap
    function displayMigrationRoadmap(roadmap) {
        const roadmapContainer = document.getElementById('roadmap');
        
        if (!roadmap || !roadmap.timeline) {
            roadmapContainer.innerHTML = `
                <div class="text-center py-8 text-gray-500">
                    Roadmap information not available
                </div>
            `;
            return;
        }

        let html = `
            <div class="bg-gray-50 p-6 rounded-lg mb-6">
                <div class="grid grid-cols-2 md:grid-cols-4 gap-4">
                    <div>
                        <h4 class="text-sm font-medium text-gray-500">Project Duration</h4>
                        <p class="text-lg font-semibold">${roadmap.projectSummary.duration}</p>
                    </div>
                    <div>
                        <h4 class="text-sm font-medium text-gray-500">Total Effort</h4>
                        <p class="text-lg font-semibold">${formatNumber(roadmap.projectSummary.totalEffort)} hours</p>
                    </div>
                    <div>
                        <h4 class="text-sm font-medium text-gray-500">Start Date</h4>
                        <p class="text-lg font-semibold">${formatDate(roadmap.projectSummary.startDate)}</p>
                    </div>
                    <div>
                        <h4 class="text-sm font-medium text-gray-500">End Date</h4>
                        <p class="text-lg font-semibold">${formatDate(roadmap.projectSummary.endDate)}</p>
                    </div>
                </div>
            </div>
        `;

        html += '<div class="space-y-8">';
        roadmap.timeline.forEach((phase, index) => {
            html += createPhaseElement(phase, index === roadmap.timeline.length - 1);
        });
        html += '</div>';
        
        roadmapContainer.innerHTML = html;
    }

    function createPhaseElement(phase, isLast) {
        return `
            <div class="relative pl-8 pb-8 border-l-2 border-blue-300 ${isLast ? 'border-l-0' : ''}">
                <div class="absolute -left-2 top-0 w-4 h-4 rounded-full ${phase.criticalPath ? 'bg-red-500' : 'bg-blue-500'}"></div>
                <div class="bg-white rounded-lg shadow-sm p-6">
                    <div class="flex justify-between items-start mb-4">
                        <div>
                            <h3 class="text-lg font-semibold ${phase.criticalPath ? 'text-red-800' : 'text-blue-800'}">${phase.name}</h3>
                            <p class="text-sm text-gray-600 mt-1">
                                ${formatDate(phase.startDate)} - ${formatDate(phase.endDate)}
                                <span class="ml-2 px-2 py-1 bg-blue-100 text-blue-800 rounded-full text-xs">
                                    ${phase.duration}
                                </span>
                            </p>
                        </div>
                        <span class="px-3 py-1 rounded-full text-sm font-medium ${getComplexityClass(phase.complexity)}">
                            ${phase.strategy || 'Phase'}
                        </span>
                    </div>
                    
                    <div class="mt-4 space-y-4">
                        ${createTasksList(phase.tasks)}
                        ${createDeliverablesList(phase.deliverables)}
                        ${createRisksList(phase.risks)}
                    </div>
                </div>
            </div>
        `;
    }

    function formatDate(dateStr) {
        return new Date(dateStr).toLocaleDateString('en-IN', {
            year: 'numeric',
            month: 'short',
            day: 'numeric'
        });
    }

    // Helper functions for roadmap section
    function createTasksList(tasks) {
        if (!tasks || !tasks.length) return '';
        return `
            <div class="border-l-2 border-gray-200 pl-4">
                <h4 class="font-medium text-gray-800">Tasks</h4>
                <ul class="mt-2 space-y-1">
                    ${tasks.map(task => `
                        <li class="text-sm text-gray-600">• ${task}</li>
                    `).join('')}
                </ul>
            </div>
        `;
    }

    function createDeliverablesList(deliverables) {
        if (!deliverables || !deliverables.length) return '';
        return `
            <div class="border-l-2 border-gray-200 pl-4">
                <h4 class="font-medium text-gray-800">Deliverables</h4>
                <ul class="mt-2 space-y-1">
                    ${deliverables.map(item => `
                        <li class="text-sm text-gray-600">✓ ${item}</li>
                    `).join('')}
                </ul>
            </div>
        `;
    }

    function createRisksList(risks) {
        if (!risks || !risks.length) return '';
        return `
            <div class="border-l-2 border-gray-200 pl-4">
                <h4 class="font-medium text-gray-800">Risks</h4>
                <ul class="mt-2 space-y-1">
                    ${risks.map(risk => `
                        <li class="text-sm text-gray-600">⚠ ${risk}</li>
                    `).join('')}
                </ul>
            </div>
        `;
    }

    // UI State Management Functions
    function showLoading() {
        loading.classList.remove('hidden');
    }

    function hideLoading() {
        loading.classList.add('hidden');
    }

    function showError(message) {
        error.classList.remove('hidden');
        errorMessage.textContent = message;
    }

    function hideError() {
        error.classList.add('hidden');
        errorMessage.textContent = '';
    }

    function showResults() {
        results.classList.remove('hidden');
    }

    function hideResults() {
        results.classList.add('hidden');
    }
});
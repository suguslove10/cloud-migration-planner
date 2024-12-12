import json
import boto3
import os
from datetime import datetime, timedelta

def generate_timeline(servers, start_date=None):
    """Generate detailed migration timeline"""
    if not start_date:
        start_date = datetime.now()

    # Sort servers by complexity and dependencies
    sorted_servers = sort_servers_by_priority(servers)
    timeline = []
    current_date = start_date

    for server in sorted_servers:
        # Calculate duration based on strategy and complexity
        duration = calculate_phase_duration(server)
        
        # Generate phases
        phases = generate_detailed_phases(server, current_date)
        
        timeline_entry = {
            'serverId': server['serverData']['serverId'],
            'serverName': server['serverData']['serverName'],
            'startDate': current_date.strftime('%Y-%m-%d'),
            'endDate': (current_date + duration).strftime('%Y-%m-%d'),
            'duration': f"{duration.days} days",
            'strategy': server['migrationStrategy']['strategy'],
            'complexity': server['complexity']['level'],
            'phases': phases,
            'riskLevel': server['migrationStrategy']['risk_level'],
            'dependencies': server['serverData']['dependencies'],
            'estimatedEffort': calculate_effort(server),
            'criticalPath': is_critical_path(server, sorted_servers)
        }
        
        timeline.append(timeline_entry)
        current_date += duration + timedelta(weeks=1)  # 1 week buffer between servers

    return timeline

def sort_servers_by_priority(servers):
    """Sort servers based on complexity, dependencies, and criticality"""
    # Create dependency graph
    dependency_graph = {}
    for server in servers:
        server_id = server['serverData']['serverId']
        dependency_graph[server_id] = {
            'server': server,
            'dependencies': server['serverData']['dependencies'],
            'complexity_score': calculate_complexity_score(server)
        }

    # Calculate priority scores
    for server_id in dependency_graph:
        dependency_graph[server_id]['priority'] = calculate_priority_score(
            server_id, 
            dependency_graph
        )

    # Sort based on priority and complexity
    sorted_servers = sorted(
        servers,
        key=lambda s: (
            calculate_priority_score(s['serverData']['serverId'], dependency_graph),
            -calculate_complexity_score(s)  # Negative for descending order
        )
    )

    return sorted_servers

def calculate_complexity_score(server):
    """Calculate numerical complexity score"""
    base_score = server['complexity']['score']
    
    # Add weight for number of dependencies
    dependency_score = len(server['serverData']['dependencies']) * 2
    
    # Add weight for resource utilization
    utilization_score = (
        server['serverData']['metrics']['cpu']['utilization'] +
        (server['serverData']['metrics']['memory']['used'] / 
         server['serverData']['metrics']['memory']['total'] * 100) +
        (server['serverData']['metrics']['storage']['used'] / 
         server['serverData']['metrics']['storage']['total'] * 100)
    ) / 3

    return base_score + dependency_score + (utilization_score * 0.5)

def calculate_priority_score(server_id, dependency_graph, visited=None):
    """Calculate priority score based on dependencies"""
    if visited is None:
        visited = set()

    if server_id in visited:
        return 0

    visited.add(server_id)
    server_node = dependency_graph.get(server_id, {})
    
    # Base priority from complexity
    priority = server_node.get('complexity_score', 0)
    
    # Add scores from dependent servers
    for dep_id in server_node.get('dependencies', []):
        if dep_id in dependency_graph:
            priority += calculate_priority_score(dep_id, dependency_graph, visited)

    return priority

def calculate_phase_duration(server):
    """Calculate duration for each migration phase"""
    base_durations = {
        'Rehost': timedelta(weeks=4),
        'Replatform': timedelta(weeks=8),
        'Refactor': timedelta(weeks=12)
    }

    # Get base duration for strategy
    base_duration = base_durations.get(
        server['migrationStrategy']['strategy'],
        timedelta(weeks=6)
    )

    # Adjust based on complexity
    complexity_multipliers = {
        'Low': 0.8,
        'Medium': 1.0,
        'High': 1.5
    }
    multiplier = complexity_multipliers.get(server['complexity']['level'], 1.0)

    # Adjust based on number of dependencies
    dep_count = len(server['serverData']['dependencies'])
    dependency_factor = 1.0 + (dep_count * 0.1)  # 10% increase per dependency

    return base_duration * multiplier * dependency_factor

def generate_detailed_phases(server, start_date):
    """Generate detailed migration phases"""
    strategy = server['migrationStrategy']['strategy']
    phase_templates = {
        'Rehost': [
            ('Planning & Assessment', 0.15, [
                'Infrastructure assessment',
                'Dependency mapping',
                'Migration plan creation',
                'Risk assessment'
            ]),
            ('Environment Preparation', 0.20, [
                'Target environment setup',
                'Network configuration',
                'Security setup',
                'Monitoring setup'
            ]),
            ('Data Migration', 0.25, [
                'Data transfer planning',
                'Initial data sync',
                'Delta sync testing',
                'Performance optimization'
            ]),
            ('Application Migration', 0.25, [
                'Application installation',
                'Configuration migration',
                'Integration testing',
                'Performance testing'
            ]),
            ('Cutover & Validation', 0.15, [
                'Final data sync',
                'DNS cutover',
                'Validation testing',
                'Performance monitoring'
            ])
        ],
        'Replatform': [
            ('Analysis & Design', 0.20, [
                'Current architecture analysis',
                'Target architecture design',
                'Gap analysis',
                'Migration strategy refinement'
            ]),
            ('Environment Setup', 0.15, [
                'Cloud infrastructure setup',
                'Platform configuration',
                'Security implementation',
                'Monitoring setup'
            ]),
            ('Application Modification', 0.30, [
                'Code modifications',
                'Database optimization',
                'Integration updates',
                'Performance tuning'
            ]),
            ('Testing', 0.20, [
                'Unit testing',
                'Integration testing',
                'Performance testing',
                'User acceptance testing'
            ]),
            ('Deployment', 0.15, [
                'Staged rollout',
                'Data migration',
                'Production deployment',
                'Post-deployment validation'
            ])
        ],
        'Refactor': [
            ('Architecture Design', 0.20, [
                'Current state analysis',
                'Future state architecture',
                'Technology selection',
                'Implementation planning'
            ]),
            ('Development Setup', 0.15, [
                'Development environment',
                'CI/CD pipeline setup',
                'Code repository setup',
                'Tool configuration'
            ]),
            ('Implementation', 0.35, [
                'Service implementation',
                'Database migration',
                'API development',
                'Integration implementation'
            ]),
            ('Testing & QA', 0.20, [
                'Unit testing',
                'Integration testing',
                'Performance testing',
                'Security testing'
            ]),
            ('Production Release', 0.10, [
                'Production environment setup',
                'Data migration',
                'Phased deployment',
                'Production validation'
            ])
        ]
    }

    phases = []
    current_date = start_date
    total_duration = calculate_phase_duration(server)
    phase_template = phase_templates.get(strategy, phase_templates['Rehost'])

    for phase_name, duration_ratio, tasks in phase_template:
        phase_duration = timedelta(seconds=total_duration.total_seconds() * duration_ratio)
        
        phases.append({
            'name': phase_name,
            'startDate': current_date.strftime('%Y-%m-%d'),
            'endDate': (current_date + phase_duration).strftime('%Y-%m-%d'),
            'duration': str(phase_duration.days) + ' days',
            'tasks': tasks,
            'completionCriteria': generate_completion_criteria(phase_name, strategy),
            'risks': generate_risk_assessment(phase_name, strategy, server)
        })
        
        current_date += phase_duration

    return phases

def generate_completion_criteria(phase_name, strategy):
    """Generate completion criteria for each phase"""
    criteria_templates = {
        'Planning & Assessment': [
            'Architecture documentation completed and approved',
            'All dependencies mapped and validated',
            'Migration plan approved by stakeholders',
            'Risk mitigation strategies defined'
        ],
        'Environment Preparation': [
            'Target environment fully configured and tested',
            'Network connectivity validated',
            'Security controls implemented and verified',
            'Monitoring tools configured and operational'
        ],
        'Data Migration': [
            'All data successfully migrated and verified',
            'Data integrity checks passed',
            'Performance benchmarks met',
            'Rollback procedures tested'
        ],
        'Application Migration': [
            'All applications successfully migrated',
            'Integration tests passed',
            'Performance requirements met',
            'User acceptance criteria fulfilled'
        ],
        'Testing & QA': [
            'All test cases executed successfully',
            'Performance criteria met',
            'Security requirements validated',
            'Stakeholder sign-off received'
        ],
        'Production Release': [
            'Production environment validated',
            'All critical functionalities operational',
            'Monitoring and alerts configured',
            'Documentation completed'
        ]
    }
    
    return criteria_templates.get(phase_name, [
        'Phase objectives achieved',
        'Quality gates passed',
        'Stakeholder approval received',
        'Documentation completed'
    ])

def generate_risk_assessment(phase_name, strategy, server):
    """Generate risk assessment for each phase"""
    base_risks = {
        'Planning & Assessment': [
            'Incomplete dependency mapping',
            'Underestimated complexity',
            'Missing critical requirements'
        ],
        'Environment Preparation': [
            'Network connectivity issues',
            'Security compliance gaps',
            'Resource availability constraints'
        ],
        'Data Migration': [
            'Data corruption during transfer',
            'Extended downtime requirements',
            'Performance degradation'
        ],
        'Application Migration': [
            'Application compatibility issues',
            'Integration failures',
            'Performance bottlenecks'
        ],
        'Testing & QA': [
            'Insufficient test coverage',
            'Undetected critical issues',
            'User acceptance delays'
        ],
        'Production Release': [
            'Production environment issues',
            'Rollback complications',
            'Business continuity risks'
        ]
    }

    # Get base risks for the phase
    risks = base_risks.get(phase_name, ['Standard execution risks'])

    # Add complexity-based risks
    if server['complexity']['level'] == 'High':
        risks.append('High complexity mitigation required')
        risks.append('Extended timeline risk')
    
    # Add dependency-based risks
    if len(server['serverData']['dependencies']) > 2:
        risks.append('Multiple dependency coordination required')
    
    return risks

def calculate_effort(server):
    """Calculate estimated effort in person-hours"""
    base_effort = {
        'Rehost': 160,      # 4 weeks, 1 person
        'Replatform': 480,  # 12 weeks, 1 person
        'Refactor': 960     # 24 weeks, 1 person
    }

    strategy = server['migrationStrategy']['strategy']
    base = base_effort.get(strategy, 320)
    
    # Adjust for complexity
    complexity_multipliers = {
        'Low': 0.8,
        'Medium': 1.0,
        'High': 1.5
    }
    
    multiplier = complexity_multipliers.get(server['complexity']['level'], 1.0)
    
    # Adjust for dependencies
    dependency_factor = 1 + (len(server['serverData']['dependencies']) * 0.15)
    
    return round(base * multiplier * dependency_factor)

def is_critical_path(server, all_servers):
    """Determine if server is on critical path"""
    # Server is on critical path if:
    # 1. It has many dependents
    # 2. It's high complexity
    # 3. It has high resource utilization
    
    dependent_count = sum(
        1 for s in all_servers 
        if server['serverData']['serverId'] in s['serverData']['dependencies']
    )
    
    is_critical = (
        dependent_count >= 2 or
        server['complexity']['level'] == 'High' or
        server['serverData']['metrics']['cpu']['utilization'] > 80
    )
    
    return is_critical

def lambda_handler(event, context):
    try:
        # Parse input data
        input_data = json.loads(event['body'])
        servers = input_data.get('servers', [])
        
        # Generate migration timeline
        timeline = generate_timeline(servers)
        
        # Calculate overall project metrics
        start_date = datetime.strptime(timeline[0]['startDate'], '%Y-%m-%d')
        end_date = datetime.strptime(timeline[-1]['endDate'], '%Y-%m-%d')
        
        # Generate project summary
        project_summary = {
            'startDate': timeline[0]['startDate'],
            'endDate': timeline[-1]['endDate'],
            'duration': str(end_date - start_date),
            'totalServers': len(servers),
            'strategyBreakdown': {
                strategy: len([s for s in servers if s['migrationStrategy']['strategy'] == strategy])
                for strategy in ['Rehost', 'Replatform', 'Refactor']
            },
            'riskProfile': {
                'high': len([s for s in servers if s['complexity']['level'] == 'High']),
                'medium': len([s for s in servers if s['complexity']['level'] == 'Medium']),
                'low': len([s for s in servers if s['complexity']['level'] == 'Low'])
            },
            'criticalPath': [
                server['serverName'] for server in timeline 
                if is_critical_path(server, servers)
            ],
            'totalEffort': sum(server['estimatedEffort'] for server in timeline),
            'keyMilestones': generate_key_milestones(timeline)
        }
        
        response_data = {
            'timeline': timeline,
            'projectSummary': project_summary
        }
        
        return {
            'statusCode': 200,
            'body': json.dumps(response_data),
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            }
        }
        
    except Exception as e:
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            }),
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            }
        }

def generate_key_milestones(timeline):
    """Generate key project milestones"""
    milestones = [
        {
            'name': 'Project Kickoff',
            'date': timeline[0]['startDate'],
            'description': 'Project initiation and team onboarding'
        }
    ]
    
    # Add critical server migrations
    for server in timeline:
        if server.get('criticalPath'):
            milestones.append({
                'name': f"{server['serverName']} Migration",
                'date': server['startDate'],
                'description': f"Begin migration of critical server {server['serverName']}"
            })
            milestones.append({
                'name': f"{server['serverName']} Completion",
                'date': server['endDate'],
                'description': f"Complete migration of critical server {server['serverName']}"
            })
    
    # Add project completion
    milestones.append({
        'name': 'Project Completion',
        'date': timeline[-1]['endDate'],
        'description': 'All migration activities completed'
    })
    
    return milestones
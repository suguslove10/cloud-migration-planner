import json
import boto3
import os
from datetime import datetime
from decimal import Decimal

# USD to INR conversion rate (you might want to make this dynamic)
USD_TO_INR = 83.0

def convert_to_inr(usd_amount):
    """Convert USD amount to INR"""
    return round(usd_amount * USD_TO_INR, 2)

def validate_input(server_data):
    """Validate server input data"""
    required_metrics = ['cpu', 'memory', 'storage']
    
    if not server_data:
        raise ValueError("Server data is required")
        
    metrics = server_data.get('metrics', {})
    
    for metric in required_metrics:
        if metric not in metrics:
            raise ValueError(f"Missing {metric} metrics")
            
    # Validate CPU metrics
    cpu = metrics['cpu']
    if not isinstance(cpu.get('cores'), (int, float)) or cpu['cores'] <= 0:
        raise ValueError("Invalid CPU cores value")
    if not isinstance(cpu.get('utilization'), (int, float)) or not 0 <= cpu['utilization'] <= 100:
        raise ValueError("Invalid CPU utilization value")
        
    # Validate memory metrics
    memory = metrics['memory']
    if not isinstance(memory.get('total'), (int, float)) or memory['total'] <= 0:
        raise ValueError("Invalid memory total value")
    if not isinstance(memory.get('used'), (int, float)) or memory['used'] < 0:
        raise ValueError("Invalid memory used value")
        
    # Validate storage metrics
    storage = metrics['storage']
    if not isinstance(storage.get('total'), (int, float)) or storage['total'] <= 0:
        raise ValueError("Invalid storage total value")
    if not isinstance(storage.get('used'), (int, float)) or storage['used'] < 0:
        raise ValueError("Invalid storage used value")

def convert_to_gb(value_in_kb):
    """Convert KB to GB"""
    return value_in_kb / (1024 * 1024)

def calculate_instance_costs(cpu_cores, memory_gb, utilization):
    """Calculate EC2 instance costs for ap-south-1 (Mumbai) region"""
    # Prices in USD for Mumbai region
    instance_pricing = {
        't3.micro': {'cpu': 2, 'memory': 1, 'hourly': 0.0113},
        't3.small': {'cpu': 2, 'memory': 2, 'hourly': 0.0226},
        't3.medium': {'cpu': 2, 'memory': 4, 'hourly': 0.0452},
        't3.large': {'cpu': 2, 'memory': 8, 'hourly': 0.0904},
        't3.xlarge': {'cpu': 4, 'memory': 16, 'hourly': 0.1808},
        't3.2xlarge': {'cpu': 8, 'memory': 32, 'hourly': 0.3616},
        'c5.xlarge': {'cpu': 4, 'memory': 8, 'hourly': 0.1890},
        'c5.2xlarge': {'cpu': 8, 'memory': 16, 'hourly': 0.3780},
        'r5.xlarge': {'cpu': 4, 'memory': 32, 'hourly': 0.2810},
        'r5.2xlarge': {'cpu': 8, 'memory': 64, 'hourly': 0.5620}
    }

    # Add 20% buffer for growth
    required_cpu = max(1, cpu_cores * (utilization / 100) * 1.2)
    required_memory = max(1, memory_gb * 1.2)

    suitable_instances = [
        (instance_type, specs)
        for instance_type, specs in instance_pricing.items()
        if specs['cpu'] >= required_cpu and specs['memory'] >= required_memory
    ]

    if not suitable_instances:
        instance_type = 'r5.2xlarge'
        specs = instance_pricing['r5.2xlarge']
    else:
        instance_type, specs = min(suitable_instances, key=lambda x: x[1]['hourly'])

    monthly_cost_usd = specs['hourly'] * 730
    monthly_cost_inr = convert_to_inr(monthly_cost_usd)

    return {
        'instanceType': instance_type,
        'monthlyCost': monthly_cost_inr,
        'specs': {
            'cpu': specs['cpu'],
            'memory': specs['memory'],
            'hourlyCost': convert_to_inr(specs['hourly'])
        }
    }

def calculate_storage_costs(storage_gb):
    """Calculate storage costs in INR"""
    # EBS pricing for Mumbai region (in USD)
    GP3_PRICE_USD = 0.0924  # per GB-month
    IO1_PRICE_USD = 0.1425  # per GB-month
    
    # Convert to INR
    GP3_PRICE = convert_to_inr(GP3_PRICE_USD)
    IO1_PRICE = convert_to_inr(IO1_PRICE_USD)
    
    if storage_gb <= 1000:
        storage_cost = storage_gb * GP3_PRICE
        storage_type = 'gp3'
    else:
        storage_cost = storage_gb * IO1_PRICE
        storage_type = 'io1'
    
    return {
        'type': storage_type,
        'sizeGB': round(storage_gb, 2),
        'monthlyCost': round(storage_cost, 2)
    }

def calculate_migration_costs(server_data):
    """Calculate migration costs based on server complexity"""
    # Base costs in INR
    base_costs = {
        'Rehost': convert_to_inr(5000),      # Lift and shift
        'Replatform': convert_to_inr(15000), # Partial optimization
        'Refactor': convert_to_inr(30000)    # Full modernization
    }
    
    strategy = server_data.get('migrationStrategy', 'Rehost')
    base_cost = base_costs.get(strategy, base_costs['Rehost'])
    
    # Calculate complexity score
    metrics = server_data['metrics']
    complexity_score = 0
    
    # CPU complexity
    if metrics['cpu']['cores'] > 8:
        complexity_score += 3
    elif metrics['cpu']['cores'] > 4:
        complexity_score += 2
    else:
        complexity_score += 1
        
    # Memory complexity
    memory_gb = convert_to_gb(metrics['memory']['total'])
    if memory_gb > 64:
        complexity_score += 3
    elif memory_gb > 32:
        complexity_score += 2
    else:
        complexity_score += 1
        
    # Storage complexity
    storage_gb = convert_to_gb(metrics['storage']['total'])
    if storage_gb > 1000:
        complexity_score += 3
    elif storage_gb > 500:
        complexity_score += 2
    else:
        complexity_score += 1
        
    # Adjust base cost by complexity
    complexity_multiplier = 1 + (complexity_score / 10)
    total_cost = base_cost * complexity_multiplier
    
    return {
        'baseCost': round(base_cost, 2),
        'complexityScore': complexity_score,
        'complexityMultiplier': round(complexity_multiplier, 2),
        'totalCost': round(total_cost, 2)
    }

def lambda_handler(event, context):
    try:
        # Parse input
        body = json.loads(event.get('body', '{}'))
        server_data = body.get('serverData')
        
        # Validate input
        validate_input(server_data)
        
        # Convert metrics to GB
        metrics = server_data['metrics']
        memory_gb = convert_to_gb(metrics['memory']['total'])
        storage_gb = convert_to_gb(metrics['storage']['total'])
        
        # Calculate costs
        compute_costs = calculate_instance_costs(
            metrics['cpu']['cores'],
            memory_gb,
            metrics['cpu']['utilization']
        )
        
        storage_costs = calculate_storage_costs(storage_gb)
        
        # Calculate total monthly cloud costs
        monthly_cloud_cost = compute_costs['monthlyCost'] + storage_costs['monthlyCost']
        
        # Calculate migration costs
        migration_costs = calculate_migration_costs(server_data)
        
        # Calculate ROI
        current_monthly_cost = monthly_cloud_cost * 1.4  # Assuming 40% savings
        monthly_savings = current_monthly_cost - monthly_cloud_cost
        roi_months = migration_costs['totalCost'] / monthly_savings if monthly_savings > 0 else float('inf')
        
        response = {
            'currency': 'INR',
            'currentMonthlyCost': round(current_monthly_cost, 2),
            'projectedMonthlyCost': round(monthly_cloud_cost, 2),
            'monthlySavings': round(monthly_savings, 2),
            'annualSavings': round(monthly_savings * 12, 2),
            'migrationCost': migration_costs['totalCost'],
            'roiMonths': round(roi_months, 1),
            'recommendations': {
                'compute': compute_costs,
                'storage': storage_costs
            },
            'threeYearSavings': round((monthly_savings * 36) - migration_costs['totalCost'], 2)
        }
        
        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps(response)
        }
        
    except ValueError as e:
        return {
            'statusCode': 400,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': str(e)
            })
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'error': f'Internal server error: {str(e)}'
            })
        }
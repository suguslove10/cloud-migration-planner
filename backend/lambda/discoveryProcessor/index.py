import json
import boto3
import os
from datetime import datetime
from decimal import Decimal

dynamodb = boto3.resource('dynamodb')
s3 = boto3.client('s3')
table = dynamodb.Table(os.environ['DISCOVERY_TABLE'])

def float_to_decimal(obj):
    """Convert float values to Decimal for DynamoDB"""
    if isinstance(obj, float):
        return Decimal(str(obj))
    if isinstance(obj, dict):
        return {k: float_to_decimal(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [float_to_decimal(x) for x in obj]
    return obj

def process_server_data(server_data):
    """Process raw server data and extract relevant metrics"""
    try:
        # Convert memory to bytes if provided in other units
        memory_total = server_data.get('totalMemory', 0)
        memory_used = server_data.get('usedMemory', 0)
        storage_total = server_data.get('totalStorage', 0)
        storage_used = server_data.get('usedStorage', 0)

        return {
            'serverId': server_data.get('serverId'),
            'serverName': server_data.get('serverName'),
            'metrics': {
                'cpu': {
                    'cores': float_to_decimal(server_data.get('cpuCores', 0)),
                    'utilization': float_to_decimal(server_data.get('cpuUtilization', 0))
                },
                'memory': {
                    'total': float_to_decimal(memory_total),
                    'used': float_to_decimal(memory_used)
                },
                'storage': {
                    'total': float_to_decimal(storage_total),
                    'used': float_to_decimal(storage_used)
                }
            },
            'applications': server_data.get('applications', []),
            'dependencies': server_data.get('dependencies', []),
            'networkUtilization': float_to_decimal(server_data.get('networkUtilization', {}))
        }
    except Exception as e:
        raise ValueError(f"Error processing server data: {str(e)}")

def calculate_migration_complexity(processed_data):
    """Calculate migration complexity score"""
    try:
        complexity_score = 0
        
        # CPU utilization (0-3 points)
        cpu_utilization = float(processed_data['metrics']['cpu']['utilization'])
        if cpu_utilization > 80:
            complexity_score += 3
        elif cpu_utilization > 60:
            complexity_score += 2
        else:
            complexity_score += 1

        # Memory utilization (0-3 points)
        memory_total = float(processed_data['metrics']['memory']['total'])
        memory_used = float(processed_data['metrics']['memory']['used'])
        memory_utilization = (memory_used / memory_total * 100) if memory_total > 0 else 0
        if memory_utilization > 80:
            complexity_score += 3
        elif memory_utilization > 60:
            complexity_score += 2
        else:
            complexity_score += 1

        # Storage utilization (0-3 points)
        storage_total = float(processed_data['metrics']['storage']['total'])
        storage_used = float(processed_data['metrics']['storage']['used'])
        storage_utilization = (storage_used / storage_total * 100) if storage_total > 0 else 0
        if storage_utilization > 80:
            complexity_score += 3
        elif storage_utilization > 60:
            complexity_score += 2
        else:
            complexity_score += 1

        # Dependencies (0-3 points)
        num_dependencies = len(processed_data['dependencies'])
        complexity_score += min(num_dependencies // 2, 3)

        # Applications (0-3 points)
        num_applications = len(processed_data['applications'])
        complexity_score += min(num_applications // 2, 3)

        # Network utilization (0-3 points)
        network_util = processed_data.get('networkUtilization', {}).get('averageUsage', 0)
        if network_util > 80:
            complexity_score += 3
        elif network_util > 60:
            complexity_score += 2
        else:
            complexity_score += 1

        # Calculate final complexity level
        max_possible_score = 18
        complexity_percentage = (complexity_score / max_possible_score) * 100

        return {
            'score': float_to_decimal(complexity_score),
            'percentage': float_to_decimal(complexity_percentage),
            'level': 'High' if complexity_percentage > 70 else 'Medium' if complexity_percentage > 40 else 'Low',
            'factors': {
                'cpu': float_to_decimal(cpu_utilization),
                'memory': float_to_decimal(memory_utilization),
                'storage': float_to_decimal(storage_utilization),
                'dependencies': float_to_decimal(num_dependencies),
                'applications': float_to_decimal(num_applications),
                'network': float_to_decimal(network_util)
            }
        }
    except Exception as e:
        raise ValueError(f"Error calculating complexity: {str(e)}")

def suggest_migration_strategy(processed_data, complexity):
    """Suggest migration strategy based on complexity"""
    if complexity['level'] == 'Low':
        return {
            'strategy': 'Rehost',
            'description': 'Lift-and-shift migration recommended due to low complexity and minimal dependencies.',
            'estimated_timeline': '2-4 weeks',
            'confidence_level': 'High',
            'risk_level': 'Low',
            'aws_services': [
                'AWS Application Migration Service',
                'EC2',
                'EBS',
                'VPC'
            ],
            'key_considerations': [
                'Minimal application changes required',
                'Quick migration timeline',
                'Lower initial costs',
                'Good for meeting tight deadlines'
            ]
        }
    elif complexity['level'] == 'Medium':
        return {
            'strategy': 'Replatform',
            'description': 'Modify and optimize applications during migration for better cloud-native compatibility.',
            'estimated_timeline': '1-3 months',
            'confidence_level': 'Medium',
            'risk_level': 'Medium',
            'aws_services': [
                'AWS Application Migration Service',
                'EC2',
                'RDS',
                'ECS',
                'Auto Scaling',
                'Elastic Load Balancing'
            ],
            'key_considerations': [
                'Moderate application modifications needed',
                'Balance between modernization and speed',
                'Improved cloud optimization',
                'Better scalability options'
            ]
        }
    else:
        return {
            'strategy': 'Refactor',
            'description': 'Significant re-architecture recommended to fully leverage cloud-native capabilities.',
            'estimated_timeline': '3-6 months',
            'confidence_level': 'Medium',
            'risk_level': 'High',
            'aws_services': [
                'ECS',
                'EKS',
                'Lambda',
                'RDS',
                'DynamoDB',
                'API Gateway',
                'CloudFront'
            ],
            'key_considerations': [
                'Major application redesign required',
                'Highest long-term benefits',
                'Full cloud-native capabilities',
                'Improved performance and scalability'
            ]
        }

def lambda_handler(event, context):
    try:
        # Parse incoming discovery data
        if not event.get('body'):
            raise ValueError("Missing request body")

        discovery_data = json.loads(event['body'])
        
        if not discovery_data.get('servers'):
            raise ValueError("No server data provided")
        
        # Process each server's data
        processed_servers = []
        for server in discovery_data['servers']:
            try:
                # Process raw server data
                processed_data = process_server_data(server)
                
                # Calculate migration complexity
                complexity = calculate_migration_complexity(processed_data)
                
                # Generate migration strategy
                strategy = suggest_migration_strategy(processed_data, complexity)
                
                # Combine all information
                server_assessment = {
                    'timestamp': datetime.utcnow().isoformat(),
                    'serverData': processed_data,
                    'complexity': complexity,
                    'migrationStrategy': strategy
                }
                
                processed_servers.append(server_assessment)
                
                # Store in DynamoDB
                table.put_item(Item={
                    'serverId': processed_data['serverId'],
                    'timestamp': server_assessment['timestamp'],
                    'assessment': float_to_decimal(server_assessment)
                })
                
            except Exception as e:
                print(f"Error processing server {server.get('serverId', 'unknown')}: {str(e)}")
                continue
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Successfully processed discovery data',
                'servers': processed_servers
            }, default=str),
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            }
        }
        
    except Exception as e:
        print(f"Error in lambda_handler: {str(e)}")
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
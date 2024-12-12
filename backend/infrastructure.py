import boto3
import json
import time
import zipfile
import os
from botocore.exceptions import ClientError

def check_aws_credentials():
    """Check if AWS credentials are configured"""
    try:
        boto3.client('sts').get_caller_identity()
        return True
    except Exception:
        return False

class InfrastructureManager:
    def __init__(self, region='ap-south-1'):
        self.region = region
        print(f"Using AWS region: {self.region}")
        
        # Initialize AWS clients with region
        self.s3 = boto3.client('s3', region_name=self.region)
        self.dynamodb = boto3.client('dynamodb', region_name=self.region)
        self.lambda_client = boto3.client('lambda', region_name=self.region)
        self.iam = boto3.client('iam', region_name=self.region)
        self.apigateway = boto3.client('apigatewayv2', region_name=self.region)
        
        # Load existing infrastructure details if available
        self.existing_infrastructure = self.load_existing_infrastructure()

    def load_existing_infrastructure(self):
        """Load existing infrastructure details from file"""
        try:
            with open('infrastructure_details.json', 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            return None

    def resource_exists(self, resource_type, identifier):
        """Check if a resource already exists"""
        if not self.existing_infrastructure:
            return False
        
        if resource_type in self.existing_infrastructure:
            return self.existing_infrastructure[resource_type] == identifier
        return False

    def create_s3_bucket(self):
        """Create or get existing S3 bucket"""
        if self.existing_infrastructure and 'bucket_name' in self.existing_infrastructure:
            try:
                # Check if bucket exists
                self.s3.head_bucket(Bucket=self.existing_infrastructure['bucket_name'])
                print(f"\nUsing existing S3 bucket: {self.existing_infrastructure['bucket_name']}")
                return self.existing_infrastructure['bucket_name']
            except ClientError:
                pass

        bucket_name = f"migration-planner-data-{int(time.time())}"
        print(f"\nCreating S3 bucket: {bucket_name}")
        
        try:
            # Create bucket with region constraint
            self.s3.create_bucket(
                Bucket=bucket_name,
                CreateBucketConfiguration={
                    'LocationConstraint': self.region
                }
            )

            # Add bucket versioning
            self.s3.put_bucket_versioning(
                Bucket=bucket_name,
                VersioningConfiguration={
                    'Status': 'Enabled'
                }
            )

            # Add bucket encryption
            self.s3.put_bucket_encryption(
                Bucket=bucket_name,
                ServerSideEncryptionConfiguration={
                    'Rules': [
                        {
                            'ApplyServerSideEncryptionByDefault': {
                                'SSEAlgorithm': 'AES256'
                            }
                        }
                    ]
                }
            )

            print(f"Successfully created S3 bucket: {bucket_name}")
            return bucket_name
        except Exception as e:
            print(f"Error creating S3 bucket: {str(e)}")
            raise

    def create_dynamodb_table(self):
        """Create or get existing DynamoDB table"""
        if self.existing_infrastructure and 'table_name' in self.existing_infrastructure:
            try:
                self.dynamodb.describe_table(TableName=self.existing_infrastructure['table_name'])
                print(f"\nUsing existing DynamoDB table: {self.existing_infrastructure['table_name']}")
                return self.existing_infrastructure['table_name']
            except ClientError:
                pass

        table_name = f"migration-assessments-{int(time.time())}"
        print(f"\nCreating DynamoDB table: {table_name}")
        
        try:
            self.dynamodb.create_table(
                TableName=table_name,
                KeySchema=[
                    {'AttributeName': 'serverId', 'KeyType': 'HASH'},
                    {'AttributeName': 'timestamp', 'KeyType': 'RANGE'}
                ],
                AttributeDefinitions=[
                    {'AttributeName': 'serverId', 'AttributeType': 'S'},
                    {'AttributeName': 'timestamp', 'AttributeType': 'S'}
                ],
                BillingMode='PAY_PER_REQUEST'
            )
            
            print("Waiting for DynamoDB table to be ready...")
            waiter = self.dynamodb.get_waiter('table_exists')
            waiter.wait(TableName=table_name)
            
            return table_name
        except Exception as e:
            print(f"Error creating DynamoDB table: {str(e)}")
            raise

    def create_lambda_role(self):
        """Create or get existing IAM role"""
        role_name = "migration_planner_lambda_role"
        
        try:
            # Try to get existing role
            response = self.iam.get_role(RoleName=role_name)
            print(f"\nUsing existing IAM role: {role_name}")
            return response['Role']['Arn']
        except ClientError:
            print(f"\nCreating IAM role: {role_name}")
            
            try:
                # Create role
                assume_role_policy = {
                    "Version": "2012-10-17",
                    "Statement": [{
                        "Effect": "Allow",
                        "Principal": {"Service": "lambda.amazonaws.com"},
                        "Action": "sts:AssumeRole"
                    }]
                }
                
                response = self.iam.create_role(
                    RoleName=role_name,
                    AssumeRolePolicyDocument=json.dumps(assume_role_policy)
                )
                
                # Attach policies
                self.iam.attach_role_policy(
                    RoleName=role_name,
                    PolicyArn='arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole'
                )
                
                # Create custom policy
                policy_document = {
                    "Version": "2012-10-17",
                    "Statement": [
                        {
                            "Effect": "Allow",
                            "Action": [
                                "s3:GetObject",
                                "s3:PutObject",
                                "s3:ListBucket"
                            ],
                            "Resource": ["arn:aws:s3:::*"]
                        },
                        {
                            "Effect": "Allow",
                            "Action": [
                                "dynamodb:PutItem",
                                "dynamodb:GetItem",
                                "dynamodb:Query",
                                "dynamodb:UpdateItem"
                            ],
                            "Resource": ["arn:aws:dynamodb:*:*:table/*"]
                        }
                    ]
                }
                
                self.iam.put_role_policy(
                    RoleName=role_name,
                    PolicyName="migration_planner_policy",
                    PolicyDocument=json.dumps(policy_document)
                )
                
                # Wait for role to be ready
                print("Waiting for IAM role to be ready...")
                time.sleep(10)
                
                return response['Role']['Arn']
            except Exception as e:
                print(f"Error creating IAM role: {str(e)}")
                raise

    def create_or_update_lambda_function(self, function_name, handler_file, role_arn, env_vars):
        """Create or update a Lambda function"""
        try:
            # Create ZIP file
            zip_path = f"/tmp/{function_name}.zip"
            with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
                zipf.write(handler_file, "index.py")
            
            with open(zip_path, 'rb') as f:
                zip_content = f.read()
            
            try:
                # Try to update existing function
                self.lambda_client.update_function_code(
                    FunctionName=function_name,
                    ZipFile=zip_content
                )
                
                self.lambda_client.update_function_configuration(
                    FunctionName=function_name,
                    Runtime='python3.9',
                    Role=role_arn,
                    Handler='index.lambda_handler',
                    Timeout=30,
                    MemorySize=256,
                    Environment={'Variables': env_vars}
                )
                print(f"Updated Lambda function: {function_name}")
                
            except ClientError as e:
                if e.response['Error']['Code'] == 'ResourceNotFoundException':
                    # Create new function
                    self.lambda_client.create_function(
                        FunctionName=function_name,
                        Runtime='python3.9',
                        Role=role_arn,
                        Handler='index.lambda_handler',
                        Code={'ZipFile': zip_content},
                        Timeout=30,
                        MemorySize=256,
                        Environment={'Variables': env_vars}
                    )
                    print(f"Created Lambda function: {function_name}")
                else:
                    raise
            
            # Clean up
            os.remove(zip_path)
            
            # Get function ARN
            response = self.lambda_client.get_function(FunctionName=function_name)
            return response['Configuration']['FunctionArn']
            
        except Exception as e:
            print(f"Error with Lambda function {function_name}: {str(e)}")
            raise

    def create_lambda_functions(self, role_arn, table_name):
        """Create or update all Lambda functions"""
        print("\nSetting up Lambda functions...")
        
        functions = {
            'discoveryProcessor': 'discovery_processor',
            'costEstimator': 'cost_estimator',
            'roadmapGenerator': 'roadmap_generator'
        }
        
        lambda_functions = {}
        
        for func_key, func_name in functions.items():
            function_name = f"migration-planner-{func_name}"
            handler_file = f"lambda/{func_key}/index.py"
            
            env_vars = {
                'DISCOVERY_TABLE': table_name
            }
            
            lambda_functions[func_key] = self.create_or_update_lambda_function(
                function_name,
                handler_file,
                role_arn,
                env_vars
            )
        
        return lambda_functions

    def create_or_update_api_gateway(self, lambda_functions):
        """Create or update API Gateway"""
        print("\nSetting up API Gateway...")
        
        api_name = "migration-planner-api"
        
        # Try to find existing API
        try:
            apis = self.apigateway.get_apis()
            existing_api = next(
                (api for api in apis['Items'] if api['Name'] == api_name),
                None
            )
            
            if existing_api:
                print(f"Using existing API Gateway: {api_name}")
                api_id = existing_api['ApiId']
                
                # Update routes
                self.update_api_routes(api_id, lambda_functions)
                
                return f"https://{api_id}.execute-api.{self.region}.amazonaws.com/prod"
        except Exception:
            pass
        
        # Create new API
        try:
            # Create API
            api_response = self.apigateway.create_api(
                Name=api_name,
                ProtocolType='HTTP',
                CorsConfiguration={
                    'AllowOrigins': ['*'],
                    'AllowMethods': ['POST', 'GET', 'OPTIONS'],
                    'AllowHeaders': ['content-type']
                }
            )
            
            api_id = api_response['ApiId']
            
            # Create stage
            self.apigateway.create_stage(
                ApiId=api_id,
                StageName='prod',
                AutoDeploy=True
            )
            
            # Create routes
            self.update_api_routes(api_id, lambda_functions)
            
            api_url = f"https://{api_id}.execute-api.{self.region}.amazonaws.com/prod"
            return api_url
            
        except Exception as e:
            print(f"Error creating API Gateway: {str(e)}")
            raise

    def update_api_routes(self, api_id, lambda_functions):
        """Update API Gateway routes"""
        routes = {
            'analyze': lambda_functions['discoveryProcessor'],
            'estimate': lambda_functions['costEstimator'],
            'roadmap': lambda_functions['roadmapGenerator']
        }
        
        for route_name, function_arn in routes.items():
            # Create integration
            integration = self.apigateway.create_integration(
                ApiId=api_id,
                IntegrationType='AWS_PROXY',
                IntegrationUri=function_arn,
                PayloadFormatVersion='2.0',
                IntegrationMethod='POST'
            )
            
            # Create route
            self.apigateway.create_route(
                ApiId=api_id,
                RouteKey=f"POST /{route_name}",
                Target=f"integrations/{integration['IntegrationId']}"
            )
            
            # Add Lambda permission
            function_name = function_arn.split(':')[-1]
            try:
                self.lambda_client.add_permission(
                    FunctionName=function_name,
                    StatementId=f'ApiGateway-{route_name}',
                    Action='lambda:InvokeFunction',
                    Principal='apigateway.amazonaws.com',
                    SourceArn=f'arn:aws:execute-api:{self.region}:{self.get_account_id()}:{api_id}/*/*'
                )
            except ClientError as e:
                if e.response['Error']['Code'] != 'ResourceConflictException':
                    raise

    def create_infrastructure(self):
        """Create or update infrastructure"""
        print("Starting infrastructure setup...")
        
        try:
            # Create or get S3 bucket
            bucket_name = self.create_s3_bucket()
            
            # Create or get DynamoDB table
            table_name = self.create_dynamodb_table()
            
            # Create or get IAM role
            role_arn = self.create_lambda_role()
            
            # Create or update Lambda functions
            lambda_functions = self.create_lambda_functions(role_arn, table_name)
            
            # Create or update API Gateway
            api_url = self.create_or_update_api_gateway(lambda_functions)
            
            # Save infrastructure details
            infra_details = {
                'api_url': api_url,
                'bucket_name': bucket_name,
                'table_name': table_name
            }
            
            print("\nInfrastructure setup completed!")
            print(f"API Gateway URL: {api_url}")
            print(f"S3 Bucket: {bucket_name}")
            print(f"DynamoDB Table: {table_name}")
            
            return infra_details
            
        except Exception as e:
            print(f"Error during infrastructure setup: {str(e)}")
            raise

    def get_account_id(self):
        """Get AWS account ID"""
        return boto3.client('sts').get_caller_identity()['Account']

    def setup_environment_file(self, api_url):
        """Create or update .env file with API Gateway URL"""
        frontend_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'frontend')
        env_file_path = os.path.join(frontend_dir, '.env')

        # Create frontend directory if it doesn't exist
        os.makedirs(frontend_dir, exist_ok=True)

        env_content = {
            'API_GATEWAY_URL': api_url,
            'AWS_REGION': self.region,
            'FLASK_ENV': 'development'
        }

        # Read existing .env if it exists
        existing_env = {}
        if os.path.exists(env_file_path):
            with open(env_file_path, 'r') as f:
                for line in f:
                    if '=' in line:
                        key, value = line.strip().split('=', 1)
                        existing_env[key] = value

        # Update only new values, preserve existing ones
        existing_env.update(env_content)

        # Write the updated content to .env file
        with open(env_file_path, 'w') as f:
            for key, value in existing_env.items():
                f.write(f"{key}={value}\n")

        print(f"\nEnvironment file updated: {env_file_path}")
        print("Note: Please manually add your AWS credentials to the .env file if needed:")
        print("AWS_ACCESS_KEY_ID=your_access_key")
        print("AWS_SECRET_ACCESS_KEY=your_secret_key")

    def clean_up_resources(self):
        """Clean up resources if needed"""
        try:
            print("\nCleaning up old resources...")
            
            # List and delete old Lambda functions
            functions = self.lambda_client.list_functions()
            for function in functions['Functions']:
                if function['FunctionName'].startswith('migration-planner-') and \
                   function['FunctionName'] not in [f"migration-planner-{name}" for name in ['discovery_processor', 'cost_estimator', 'roadmap_generator']]:
                    try:
                        self.lambda_client.delete_function(FunctionName=function['FunctionName'])
                        print(f"Deleted old Lambda function: {function['FunctionName']}")
                    except Exception as e:
                        print(f"Error deleting Lambda function {function['FunctionName']}: {str(e)}")

            # List and delete old API Gateways
            apis = self.apigateway.get_apis()
            for api in apis['Items']:
                if api['Name'].startswith('migration-planner-api-') and \
                   api['Name'] != 'migration-planner-api':
                    try:
                        self.apigateway.delete_api(ApiId=api['ApiId'])
                        print(f"Deleted old API Gateway: {api['Name']}")
                    except Exception as e:
                        print(f"Error deleting API Gateway {api['Name']}: {str(e)}")

        except Exception as e:
            print(f"Error during cleanup: {str(e)}")

    def get_account_id(self):
        """Get AWS account ID"""
        return boto3.client('sts').get_caller_identity()['Account']


def check_aws_credentials():
    """Check if AWS credentials are configured"""
    try:
        boto3.client('sts').get_caller_identity()
        return True
    except Exception:
        return False


def main():
    # Check AWS credentials
    if not check_aws_credentials():
        print("Error: AWS credentials not found or not configured.")
        print("Please run 'aws configure' to set up your AWS credentials first.")
        return

    try:
        # Create infrastructure manager
        infra_manager = InfrastructureManager()
        
        # Create or update infrastructure
        infra_details = infra_manager.create_infrastructure()
        
        # Save infrastructure details to file
        with open('infrastructure_details.json', 'w') as f:
            json.dump(infra_details, f, indent=2)
        
        # Setup environment file
        infra_manager.setup_environment_file(infra_details['api_url'])
        
        print("\nSetup completed successfully!")
        print("1. Infrastructure details saved to infrastructure_details.json")
        print("2. Environment variables configured in frontend/.env")
        print("3. Please add your AWS credentials to frontend/.env if needed")
        print("\nYou can now run the Flask application:")
        print("cd ../frontend")
        print("python app.py")
        
    except Exception as e:
        print(f"\nError during setup: {str(e)}")
        print("Please check the error message and try again.")


if __name__ == "__main__":
    main()
import boto3
from botocore.exceptions import ClientError
import os

def delete_lambda_functions(lambda_client):
    """🗑️ Delete all Lambda functions starting with 'migration-planner-'"""
    functions = lambda_client.list_functions()
    for function in functions['Functions']:
        if function['FunctionName'].startswith('migration-planner-'):
            try:
                lambda_client.delete_function(FunctionName=function['FunctionName'])
                print(f"✅ Deleted Lambda function: {function['FunctionName']}")
            except ClientError as e:
                print(f"❌ Error deleting Lambda function {function['FunctionName']}: {str(e)}")

def delete_api_gateways(apigateway_client):
    """🗑️ Delete all API Gateways starting with 'migration-planner-api'"""
    apis = apigateway_client.get_apis()
    for api in apis['Items']:
        if api['Name'].startswith('migration-planner-api'):
            try:
                apigateway_client.delete_api(ApiId=api['ApiId'])
                print(f"✅ Deleted API Gateway: {api['Name']}")
            except ClientError as e:
                print(f"❌ Error deleting API Gateway {api['Name']}: {str(e)}")

def delete_dynamodb_tables(dynamodb_client):
    """🗑️ Delete all DynamoDB tables starting with 'migration-assessments-'"""
    response = dynamodb_client.list_tables()
    for table_name in response['TableNames']:
        if table_name.startswith('migration-assessments-'):
            try:
                dynamodb_client.delete_table(TableName=table_name)
                print(f"✅ Deleted DynamoDB table: {table_name}")
            except ClientError as e:
                print(f"❌ Error deleting DynamoDB table {table_name}: {str(e)}")

def delete_s3_buckets(s3_client):
    """🗑️ Delete all S3 buckets starting with 'migration-planner-data-'"""
    response = s3_client.list_buckets()
    for bucket in response['Buckets']:
        if bucket['Name'].startswith('migration-planner-data-'):
            try:
                # Delete all objects in the bucket
                objects = s3_client.list_objects_v2(Bucket=bucket['Name'])
                if 'Contents' in objects:
                    delete_keys = {'Objects': [{'Key': obj['Key']} for obj in objects['Contents']]}
                    s3_client.delete_objects(Bucket=bucket['Name'], Delete=delete_keys)
                
                # Delete the bucket
                s3_client.delete_bucket(Bucket=bucket['Name'])
                print(f"✅ Deleted S3 bucket: {bucket['Name']}")
            except ClientError as e:
                print(f"❌ Error deleting S3 bucket {bucket['Name']}: {str(e)}")

def delete_iam_roles(iam_client):
    """🗑️ Delete IAM role 'migration_planner_lambda_role'"""
    role_name = 'migration_planner_lambda_role'
    try:
        # Detach policies from the role
        response = iam_client.list_attached_role_policies(RoleName=role_name)
        for policy in response['AttachedPolicies']:
            iam_client.detach_role_policy(RoleName=role_name, PolicyArn=policy['PolicyArn'])
        
        # Delete inline policies
        response = iam_client.list_role_policies(RoleName=role_name)
        for policy_name in response['PolicyNames']:
            iam_client.delete_role_policy(RoleName=role_name, PolicyName=policy_name)
        
        # Delete the role
        iam_client.delete_role(RoleName=role_name)
        print(f"✅ Deleted IAM role: {role_name}")
    except ClientError as e:
        print(f"❌ Error deleting IAM role {role_name}: {str(e)}")

def delete_infrastructure_file():
    """🗑️ Delete the 'infrastructure_details.json' file"""
    file_path = 'infrastructure_details.json'
    if os.path.exists(file_path):
        try:
            os.remove(file_path)
            print(f"✅ Deleted file: {file_path}")
        except Exception as e:
            print(f"❌ Error deleting file {file_path}: {str(e)}")
    else:
        print(f"ℹ️ File not found: {file_path}")

def main():
    region = 'ap-south-1'  # 🌍 Replace with your region
    
    session = boto3.Session(region_name=region)
    lambda_client = session.client('lambda')
    apigateway_client = session.client('apigatewayv2') 
    dynamodb_client = session.client('dynamodb')
    s3_client = session.client('s3')
    iam_client = session.client('iam')
    
    print("🚀 Starting cleanup...")
    
    delete_lambda_functions(lambda_client)
    delete_api_gateways(apigateway_client)
    delete_dynamodb_tables(dynamodb_client)
    delete_s3_buckets(s3_client)
    delete_iam_roles(iam_client)
    delete_infrastructure_file()
    
    print("🎉 Cleanup completed.")

if __name__ == "__main__":
    main()
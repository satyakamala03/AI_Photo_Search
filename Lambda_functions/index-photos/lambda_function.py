import json
import boto3
import datetime
import os
import botocore.auth
import botocore.awsrequest
import botocore.credentials
from urllib.parse import urljoin
import http.client

region = 'us-east-1'  
service = 'es'       
host = 'search-photos-2qrt2dmuwhxmm5j2xxe7exnu4y.us-east-1.es.amazonaws.com'  # <--- Replace with your actual OpenSearch endpoint (no https://)
index = 'photos'

# Create AWS service clients
s3 = boto3.client('s3')
rekognition = boto3.client('rekognition')

def lambda_handler(event, context):
    print("Received event:", json.dumps(event))

    # Extract bucket and object key
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = event['Records'][0]['s3']['object']['key']

    # Detect labels using Rekognition
    rek_response = rekognition.detect_labels(
        Image={'S3Object': {'Bucket': bucket, 'Name': key}},
        MaxLabels=10
    )
    rek_labels = [label['Name'].lower() for label in rek_response['Labels']]

    # Retrieve custom labels from S3 metadata
    metadata = s3.head_object(Bucket=bucket, Key=key).get('Metadata', {})
    custom_labels = metadata.get('customlabels', '')
    custom_labels_list = [x.strip().lower() for x in custom_labels.split(',')] if custom_labels else []

    # Combine labels
    labels = rek_labels + custom_labels_list

    # Build document
    doc = {
        "objectKey": key,
        "bucket": bucket,
        "createdTimestamp": datetime.datetime.now().isoformat(),
        "labels": labels
    }

    # Sign and send to OpenSearch
    credentials = boto3.Session().get_credentials()
    aws_request = botocore.awsrequest.AWSRequest(
        method='POST',
        url=f'https://{host}/{index}/_doc',
        data=json.dumps(doc),
        headers={'Content-Type': 'application/json'}
    )
    botocore.auth.SigV4Auth(credentials, service, region).add_auth(aws_request)

    # Send HTTPS request manually
    conn = http.client.HTTPSConnection(host)
    signed_headers = dict(aws_request.headers.items())
    conn.request('POST', f'/{index}/_doc', body=aws_request.body, headers=signed_headers)
    response = conn.getresponse()

    # Debugging output
    print(f"Status: {response.status}")
    print(f"Response: {response.read().decode()}")

    return {
        'statusCode': response.status,
        'body': 'Document indexed'
    }

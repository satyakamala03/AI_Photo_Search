import json
import boto3
import urllib3
import base64

# AWS setup
region = 'us-east-1'
host = 'search-photos-2qrt2dmuwhxmm5j2xxe7exnu4y.us-east-1.es.amazonaws.com'
index = 'photos'
http = urllib3.PoolManager()

# Basic auth for OpenSearch
username = 'hetal'
password = 'Hetal21@'

auth_string = f"{username}:{password}"
encoded_auth = base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')
basic_auth_headers = {
    'Content-Type': 'application/json',
    'Authorization': f"Basic {encoded_auth}"
}

def lambda_handler(event, context):
    print("Event received:", json.dumps(event))

    try:
        # 🛡️ CORS Preflight request
        if event.get('httpMethod', '') == 'OPTIONS':
            return build_cors_response(200, {"message": "CORS preflight success"})

        # 🌟 API Gateway call
        if 'queryStringParameters' in event:
            query = event.get('queryStringParameters', {}).get('q', '')
            response = handle_api_gateway(query)
        else:
            # 🤖 Lex bot call
            response = handle_lex(event)

    except Exception as e:
        print("Unhandled exception:", str(e))
        response = build_cors_response(500, {"error": "Internal Server Error", "message": str(e)})

    # 🛡️ Inject CORS headers into all responses
    if 'headers' not in response:
        response['headers'] = {}
    response['headers']['Access-Control-Allow-Origin'] = "*"
    response['headers']['Access-Control-Allow-Methods'] = "GET,POST,PUT,OPTIONS"
    response['headers']['Access-Control-Allow-Headers'] = "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token"

    return response

def build_cors_response(status_code, body_dict):
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET,POST,PUT,OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type,X-Amz-Date,Authorization,X-Api-Key,X-Amz-Security-Token"
        },
        "body": json.dumps(body_dict)
    }

def handle_api_gateway(query):
    print("API Gateway query received:", query)

    if not query:
        return build_cors_response(200, [])  # Empty search query → return empty list

    keywords = [word.strip().lower() for word in query.split() if word.strip()]
    photos = search_photos(keywords)

    results = [
        {
            "url": f"https://photo-album-bucket-hetal.s3.amazonaws.com/{photo['objectKey']}",
            "labels": photo['labels']
        } for photo in photos
    ]

    return build_cors_response(200, results)

def handle_lex(event):
    print("Lex event received:", json.dumps(event))

    keywords = []
    slots = event.get('sessionState', {}).get('intent', {}).get('slots', {})

    if slots and 'Label' in slots:
        label_value = slots['Label'].get('value', {}).get('interpretedValue')
        if label_value:
            keywords = [label_value.lower()]

    if not keywords and 'inputTranscript' in event:
        query = event['inputTranscript']
        keywords = [word.strip().lower() for word in query.split() if word.strip()]

    print("Extracted keywords from Lex:", keywords)

    if not keywords:
        return build_lex_response([], event, message="No keywords found.")

    photos = search_photos(keywords)

    if photos:
        names = ', '.join([p.get("objectKey", "photo") for p in photos])
        message = f"Found {len(photos)} photo(s): {names}"
    else:
        message = "No matching photos found."

    return build_lex_response(photos, event, message)

def search_photos(keywords):
    search_query = {
        "query": {
            "bool": {
                "should": [
                    {"match_phrase": {"labels": keyword}} for keyword in keywords
                ],
                "minimum_should_match": 1
            }
        }
    }

    print("OpenSearch query to send:", json.dumps(search_query))

    try:
        response = http.request(
            'POST',  # ✅ Fixed: POST because we're sending a body
            f'https://{host}/{index}/_search',
            body=json.dumps(search_query),
            headers=basic_auth_headers
        )
        raw_response = response.data.decode("utf-8")
        print("Raw OpenSearch response:", raw_response)

        result = json.loads(raw_response)
        hits = result.get('hits', {}).get('hits', [])
        photos = [hit['_source'] for hit in hits]
        print("Photos extracted:", photos)

        return photos
    
    except Exception as e:
        print("Error querying OpenSearch:", str(e))
        return []

def build_lex_response(photos, event, message):
    return {
        "sessionState": {
            "dialogAction": {
                "type": "Close"
            },
            "intent": {
                "name": "SearchIntent",
                "state": "Fulfilled"
            }
        },
        "messages": [
            {
                "contentType": "PlainText",
                "content": message
            }
        ],
        "sessionId": event.get("sessionId", "default-session"),
        "requestAttributes": event.get("requestAttributes", {}),
    }

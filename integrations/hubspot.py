import secrets
import base64
import json
import httpx
from fastapi import Request, HTTPException
from fastapi.responses import HTMLResponse
from redis_client import add_key_value_redis, get_value_redis, delete_key_redis
from integrations.integration_item import IntegrationItem

# HubSpot OAuth credentials (replace with your actual credentials)
CLIENT_ID = '8ec8cc05-5d03-4e03-9e03-04c645b0861b'  # Replace with your actual HubSpot Client ID
CLIENT_SECRET = 'e6305a3c-b6e1-4819-ba73-f67da21fe5bb'  # Replace with your actual HubSpot Client Secret
REDIRECT_URI = 'http://localhost:8000/integrations/hubspot/oauth2callback'

# HubSpot authorization URL
authorization_url = f'https://app.hubspot.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}'

async def authorize_hubspot(user_id, org_id):
    state_data = {
        'state': secrets.token_urlsafe(32),
        'user_id': user_id,
        'org_id': org_id
    }
    encoded_state = base64.urlsafe_b64encode(json.dumps(state_data).encode('utf-8')).decode('utf-8')

    # Set the required scope, for example, to access contacts
    scope = 'contacts.read deals.read'  # Update this with the actual scope you need

    # Generate the HubSpot authorization URL with the correct scope
    auth_url = f"https://app.hubspot.com/oauth/authorize?client_id={CLIENT_ID}&response_type=code&redirect_uri={REDIRECT_URI}&scope={scope}&state={encoded_state}"
    
    # Store the state for later validation
    await add_key_value_redis(f'hubspot_state:{org_id}:{user_id}', encoded_state, expire=600)

    return auth_url

    # Generate a random state value for OAuth security
    state_data = {
        'state': secrets.token_urlsafe(32),
        'user_id': user_id,
        'org_id': org_id
    }
    encoded_state = base64.urlsafe_b64encode(json.dumps(state_data).encode('utf-8')).decode('utf-8')
    
    # Store the state for later validation in Redis
    await add_key_value_redis(f'hubspot_state:{org_id}:{user_id}', encoded_state, expire=600)

    # Return the HubSpot OAuth URL with the state parameter
    auth_url = f"{authorization_url}&state={encoded_state}"
    return auth_url

async def oauth2callback_hubspot(request: Request):
    # Retrieve the authorization code and state from the query parameters
    code = request.query_params.get('code')
    encoded_state = request.query_params.get('state')
    state_data = json.loads(base64.urlsafe_b64decode(encoded_state).decode('utf-8'))

    user_id = state_data.get('user_id')
    org_id = state_data.get('org_id')

    # Validate the state stored in Redis
    saved_state = await get_value_redis(f'hubspot_state:{org_id}:{user_id}')
    if not saved_state or state_data.get('state') != json.loads(saved_state).get('state'):
        raise HTTPException(status_code=400, detail='State does not match.')

    # Exchange the authorization code for access tokens
    async with httpx.AsyncClient() as client:
        response = await client.post(
            'https://api.hubapi.com/oauth/v1/token',
            data={
                'grant_type': 'authorization_code',
                'code': code,
                'redirect_uri': REDIRECT_URI,
                'client_id': CLIENT_ID,
                'client_secret': CLIENT_SECRET,
            }
        )
        token_data = response.json()

    # Store the access token and refresh token in Redis
    await add_key_value_redis(f'hubspot_credentials:{org_id}:{user_id}', json.dumps(token_data), expire=600)

    # Close the OAuth window after success
    close_window_script = """
    <html>
        <script>
            window.close();
        </script>
    </html>
    """
    return HTMLResponse(content=close_window_script)

# Function to retrieve HubSpot credentials (access token, refresh token) from Redis
async def get_hubspot_credentials(user_id, org_id):
    credentials = await get_value_redis(f'hubspot_credentials:{org_id}:{user_id}')
    if not credentials:
        raise HTTPException(status_code=400, detail='No credentials found.')
    credentials = json.loads(credentials)
    await delete_key_redis(f'hubspot_credentials:{org_id}:{user_id}')
    return credentials

# Helper function to create an IntegrationItem metadata object
def create_integration_item_metadata_object(response_json: dict, item_type: str) -> IntegrationItem:
    integration_item_metadata = IntegrationItem(
        id=response_json.get('id', None),
        name=response_json.get('properties', {}).get('name', 'No Name'),
        type=item_type,
        creation_time=response_json.get('createdAt', 'N/A'),
        last_modified_time=response_json.get('updatedAt', 'N/A'),
    )
    return integration_item_metadata

# Function to retrieve items (e.g., Contacts, Deals) from HubSpot
async def get_items_hubspot(credentials: dict) -> list:
    access_token = credentials.get("access_token")
    url = 'https://api.hubapi.com/crm/v3/objects/contacts'  # Example API endpoint for contacts

    async with httpx.AsyncClient() as client:
        response = await client.get(url, headers={'Authorization': f'Bearer {access_token}'})
    
    items = response.json().get('results', [])
    integration_items = []

    for item in items:
        # Creating metadata for each item
        integration_item = create_integration_item_metadata_object(item, 'Contact')  # Change 'Contact' to other types if needed
        integration_items.append(integration_item)

    return integration_items

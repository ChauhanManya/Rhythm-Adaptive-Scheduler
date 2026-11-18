import json
import os
from google_auth_oauthlib.flow import Flow


CLIENT_SECRET_FOLDER = "JSON_Files/Secrets/Clients"
TOKEN_FOLDER = "JSON_Files/Tokens"
REDIRECT_URI = "https://www.google.com"
SCOPES = [
    "https://www.googleapis.com/auth/googlehealth.health_metrics_and_measurements.readonly",
    "https://www.googleapis.com/auth/googlehealth.sleep.readonly"
]


def get_oauth_token(CLIENT_SECRET_FILE):
    #error handling - if path to file does not exist then:
    if not os.path.exists(CLIENT_SECRET_FILE):
        print("ERROR: client_secret.json was not found.")
        return

    #get info from client credientials 
    flow = Flow.from_client_secrets_file(CLIENT_SECRET_FILE, scopes=SCOPES,redirect_uri=REDIRECT_URI)

    #Submit access request
    authorization_url, state = flow.authorization_url( access_type="offline",prompt="consent")

    print("Rhythm - Google Health API OAuth")
    print("\nOpen this URL in your browser:\n")
    print(authorization_url)

    redirect_response = input("\nPaste the FULL redirected URL here:\n").strip()

    flow.fetch_token(authorization_response=redirect_response)

    credentials = flow.credentials

    token_data = {
        "token": credentials.token,
        "refresh_token": credentials.refresh_token,
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": flow.client_config["client_id"],
        "client_secret": flow.client_config["client_secret"],
        "scopes": credentials.scopes
    }
    token_file = os.path.join(TOKEN_FOLDER,"token"+os.path.basename(CLIENT_SECRET_FILE)) 
    # Takes Client1_secret out of Client1_secret.json
    with open(token_file, "w") as file:
        json.dump(token_data, file, indent=2)
    
    print("OAuth successful!")
    print("\nGranted scopes:")
    for scope in credentials.scopes:
        print("  ", scope)

if __name__ == "__main__":
    # Loop through everything inside the directory
    for filename in os.listdir(CLIENT_SECRET_FOLDER ):
        # Construct the full file path
        full_path = os.path.join(CLIENT_SECRET_FOLDER, filename)
        print(f"File Name: {filename}")
        get_oauth_token(full_path)
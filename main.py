"""
Google Cloud Token Server
A FastAPI server that generates access tokens for Google Cloud Document AI
"""

import os
import json
import time
from datetime import datetime, timedelta
from typing import Optional

import jwt
import httpx
from fastapi import FastAPI, HTTPException, Depends, Security
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Google Cloud Token Server",
    description="Generate access tokens for Google Cloud Document AI",
    version="1.0.0"
)

# Security
security = HTTPBearer()

# Environment variables
API_KEY = os.getenv("API_KEY", "your-secret-api-key-here")
SERVICE_ACCOUNT_JSON = os.getenv("SERVICE_ACCOUNT_JSON")

# Google OAuth2 token endpoint
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"

# Document AI scope
SCOPES = ["https://www.googleapis.com/auth/cloud-platform"]

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    expires_at: str

class ServiceAccountCredentials:
    def __init__(self):
        self.credentials = None
        self.load_credentials()
    
    def load_credentials(self):
        """Load service account credentials from environment variable or file"""
        try:
            if SERVICE_ACCOUNT_JSON:
                # Try to parse as JSON string first
                try:
                    self.credentials = json.loads(SERVICE_ACCOUNT_JSON)
                    logger.info("Loaded credentials from SERVICE_ACCOUNT_JSON environment variable")
                except json.JSONDecodeError:
                    # Try to load as file path
                    with open(SERVICE_ACCOUNT_JSON, 'r') as f:
                        self.credentials = json.load(f)
                    logger.info(f"Loaded credentials from file: {SERVICE_ACCOUNT_JSON}")
            else:
                # Try to load from default file
                with open('service-account-key.json', 'r') as f:
                    self.credentials = json.load(f)
                logger.info("Loaded credentials from service-account-key.json")
                
        except (FileNotFoundError, json.JSONDecodeError) as e:
            logger.error(f"Failed to load service account credentials: {e}")
            raise HTTPException(
                status_code=500, 
                detail="Service account credentials not configured properly"
            )

# Initialize credentials
service_account = ServiceAccountCredentials()

def verify_api_key(credentials: HTTPAuthorizationCredentials = Security(security)):
    """Verify API key from Authorization header"""
    if credentials.credentials != API_KEY:
        raise HTTPException(
            status_code=401,
            detail="Invalid API key"
        )
    return credentials.credentials

def create_jwt_token() -> str:
    """Create a signed JWT for Google OAuth2"""
    now = int(time.time())
    
    payload = {
        "iss": service_account.credentials["client_email"],
        "sub": service_account.credentials["client_email"],
        "scope": " ".join(SCOPES),
        "aud": GOOGLE_TOKEN_URL,
        "iat": now,
        "exp": now + 3600  # 1 hour expiration
    }
    
    return jwt.encode(
        payload,
        service_account.credentials["private_key"],
        algorithm="RS256"
    )

async def exchange_jwt_for_token(jwt_token: str) -> dict:
    """Exchange JWT for access token with Google"""
    data = {
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": jwt_token
    }
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            GOOGLE_TOKEN_URL,
            data=data,
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        if response.status_code != 200:
            logger.error(f"Token exchange failed: {response.text}")
            raise HTTPException(
                status_code=500,
                detail="Failed to obtain access token from Google"
            )
        
        return response.json()

@app.get("/")
async def root():
    """Health check endpoint"""
    return {
        "message": "Google Cloud Token Server",
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat()
    }

@app.get("/health")
async def health():
    """Detailed health check"""
    try:
        # Check if credentials are loaded
        if not service_account.credentials:
            return {"status": "unhealthy", "reason": "No service account credentials"}
        
        return {
            "status": "healthy",
            "service_account_email": service_account.credentials.get("client_email"),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        return {"status": "unhealthy", "reason": str(e)}

@app.post("/token", response_model=TokenResponse)
async def get_access_token(api_key: str = Depends(verify_api_key)):
    """
    Generate a fresh Google Cloud access token for Document AI
    
    Requires API key authentication via Authorization header
    """
    try:
        # Create JWT
        jwt_token = create_jwt_token()
        
        # Exchange JWT for access token
        token_data = await exchange_jwt_for_token(jwt_token)
        
        # Calculate expiration time
        expires_in = token_data.get("expires_in", 3600)
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
        
        logger.info("Successfully generated new access token")
        
        return TokenResponse(
            access_token=token_data["access_token"],
            expires_in=expires_in,
            expires_at=expires_at.isoformat()
        )
        
    except Exception as e:
        logger.error(f"Error generating token: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate access token: {str(e)}"
        )

@app.get("/docs-info")
async def docs_info():
    """Information about using this API"""
    return {
        "usage": {
            "endpoint": "/token",
            "method": "POST", 
            "authentication": "Bearer token in Authorization header (required)",
            "example": "curl -X POST 'https://your-server.com/token' -H 'Authorization: Bearer your-api-key'"
        },
        "token_usage": {
            "description": "Use the returned access token to authenticate Google Cloud Document AI requests",
            "example": "curl -X POST 'https://documentai.googleapis.com/v1/projects/PROJECT/locations/LOCATION/processors/PROCESSOR:process' -H 'Authorization: Bearer ACCESS_TOKEN'"
        }
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
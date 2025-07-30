"""
Google Cloud Token Server
A FastAPI server that generates access tokens for Google Cloud Document AI
"""

import os
import json
import time
import signal
import asyncio
from datetime import datetime, timedelta
from typing import Optional

import jwt
import httpx
from fastapi import FastAPI, HTTPException, Depends, Security, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import logging
from dotenv import load_dotenv
import uvicorn

# Load environment variables from .env file
load_dotenv()

# Configure logging for production
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/tmp/app.log') if os.path.exists('/tmp') else logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Global shutdown event
shutdown_event = asyncio.Event()

app = FastAPI(
    title="Google Cloud Token Server",
    description="Generate access tokens for Google Cloud Document AI",
    version="1.0.0",
    docs_url="/docs" if os.getenv("ENVIRONMENT") != "production" else None,
    redoc_url="/redoc" if os.getenv("ENVIRONMENT") != "production" else None
)

# Add CORS middleware for production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure this properly for production
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# Security
security = HTTPBearer()

# Health check state
health_state = {
    "startup_time": datetime.utcnow(),
    "last_successful_token": None,
    "consecutive_failures": 0,
    "total_requests": 0,
    "successful_requests": 0
}

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
    
    # Validate required fields
    if not service_account.credentials.get("client_email"):
        raise ValueError("Service account credentials missing 'client_email'")
    if not service_account.credentials.get("private_key"):
        raise ValueError("Service account credentials missing 'private_key'")
    
    payload = {
        "iss": service_account.credentials["client_email"],
        "sub": service_account.credentials["client_email"],
        "scope": " ".join(SCOPES),
        "aud": GOOGLE_TOKEN_URL,
        "iat": now,
        "exp": now + 3600  # 1 hour expiration
    }
    
    logger.info(f"Creating JWT for service account: {service_account.credentials['client_email']}")
    
    try:
        return jwt.encode(
            payload,
            service_account.credentials["private_key"],
            algorithm="RS256"
        )
    except Exception as e:
        logger.error(f"Error creating JWT: {e}")
        raise ValueError(f"Failed to create JWT token: {str(e)}")

async def exchange_jwt_for_token(jwt_token: str) -> dict:
    """Exchange JWT for access token with Google"""
    data = {
        "grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer",
        "assertion": jwt_token
    }
    
    headers = {
        "Content-Type": "application/x-www-form-urlencoded",
        "User-Agent": "Google-Cloud-Token-Server/1.0"
    }
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            logger.info(f"Making request to {GOOGLE_TOKEN_URL}")
            response = await client.post(
                GOOGLE_TOKEN_URL,
                data=data,
                headers=headers
            )
            
            logger.info(f"Response status code: {response.status_code}")
            logger.info(f"Response headers: {dict(response.headers)}")
            
            if response.status_code != 200:
                logger.error(f"Token exchange failed with status {response.status_code}")
                logger.error(f"Response text: {response.text}")
                logger.error(f"Response headers: {dict(response.headers)}")
                
                # Provide more specific error messages
                if response.status_code == 502:
                    raise HTTPException(
                        status_code=502,
                        detail="Bad Gateway: Google's OAuth2 service is temporarily unavailable. Please try again in a few moments."
                    )
                elif response.status_code == 400:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Bad Request to Google OAuth2: {response.text}"
                    )
                else:
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=f"Google OAuth2 error ({response.status_code}): {response.text}"
                    )
            
            return response.json()
            
    except httpx.ConnectError as e:
        logger.error(f"Connection error: {e}")
        raise HTTPException(
            status_code=503,
            detail="Cannot connect to Google's OAuth2 service. Check your internet connection."
        )
    except httpx.TimeoutException as e:
        logger.error(f"Request timeout: {e}")
        raise HTTPException(
            status_code=504,
            detail="Request to Google's OAuth2 service timed out. Please try again."
        )
    except Exception as e:
        logger.error(f"Unexpected error during token exchange: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Unexpected error during token exchange: {str(e)}"
        )

@app.on_event("startup")
async def startup_event():
    """Application startup tasks"""
    logger.info("🚀 Google Cloud Token Server starting up...")
    health_state["startup_time"] = datetime.utcnow()
    
    # Test initial connectivity
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get("https://oauth2.googleapis.com/tokeninfo")
            logger.info("✅ Initial Google OAuth2 connectivity test passed")
    except Exception as e:
        logger.warning(f"⚠️ Initial connectivity test failed: {e}")

@app.on_event("shutdown")
async def shutdown_event():
    """Application shutdown tasks"""
    logger.info("🛑 Google Cloud Token Server shutting down...")
    shutdown_event.set()

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    logger.info(f"📡 Received signal {signum}, initiating graceful shutdown...")
    shutdown_event.set()

# Register signal handlers
signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

@app.get("/")
async def root():
    """Basic health check endpoint for load balancers"""
    return {
        "message": "Google Cloud Token Server",
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "uptime_seconds": int((datetime.utcnow() - health_state["startup_time"]).total_seconds())
    }

@app.get("/health")
async def health():
    """Detailed health check for monitoring systems"""
    try:
        # Check if credentials are loaded
        if not service_account.credentials:
            return {
                "status": "unhealthy", 
                "reason": "No service account credentials",
                "timestamp": datetime.utcnow().isoformat()
            }
        
        # Calculate uptime
        uptime = datetime.utcnow() - health_state["startup_time"]
        
        # Determine health status
        status = "healthy"
        issues = []
        
        # Check for consecutive failures
        if health_state["consecutive_failures"] > 5:
            status = "degraded"
            issues.append(f"High failure rate: {health_state['consecutive_failures']} consecutive failures")
        
        # Check success rate
        if health_state["total_requests"] > 0:
            success_rate = health_state["successful_requests"] / health_state["total_requests"]
            if success_rate < 0.8:
                status = "degraded"
                issues.append(f"Low success rate: {success_rate:.2%}")
        
        return {
            "status": status,
            "service_account_email": service_account.credentials.get("client_email"),
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": int(uptime.total_seconds()),
            "stats": {
                "total_requests": health_state["total_requests"],
                "successful_requests": health_state["successful_requests"],
                "consecutive_failures": health_state["consecutive_failures"],
                "last_successful_token": health_state["last_successful_token"].isoformat() if health_state["last_successful_token"] else None,
                "success_rate": health_state["successful_requests"] / max(health_state["total_requests"], 1)
            },
            "issues": issues
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy", 
            "reason": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

@app.get("/readiness")
async def readiness():
    """Kubernetes-style readiness probe"""
    try:
        # Test Google connectivity with a quick request
        async with httpx.AsyncClient(timeout=3.0) as client:
            response = await client.get("https://oauth2.googleapis.com/tokeninfo")
            
        return {
            "status": "ready",
            "timestamp": datetime.utcnow().isoformat(),
            "google_reachable": True
        }
    except Exception as e:
        return {
            "status": "not_ready",
            "reason": f"Google OAuth2 not reachable: {str(e)}",
            "timestamp": datetime.utcnow().isoformat(),
            "google_reachable": False
        }

@app.get("/liveness")
async def liveness():
    """Kubernetes-style liveness probe"""
    return {
        "status": "alive",
        "timestamp": datetime.utcnow().isoformat(),
        "uptime_seconds": int((datetime.utcnow() - health_state["startup_time"]).total_seconds())
    }

@app.post("/token", response_model=TokenResponse)
async def get_access_token(request: Request, api_key: str = Depends(verify_api_key)):
    """
    Generate a fresh Google Cloud access token for Document AI
    
    Requires API key authentication via Authorization header
    """
    health_state["total_requests"] += 1
    
    try:
        # Create JWT
        jwt_token = create_jwt_token()
        
        # Exchange JWT for access token
        token_data = await exchange_jwt_for_token(jwt_token)
        
        # Calculate expiration time
        expires_in = token_data.get("expires_in", 3600)
        expires_at = datetime.utcnow() + timedelta(seconds=expires_in)
        
        # Update health state on success
        health_state["successful_requests"] += 1
        health_state["consecutive_failures"] = 0
        health_state["last_successful_token"] = datetime.utcnow()
        
        logger.info(f"✅ Successfully generated access token for client {request.client.host if request.client else 'unknown'}")
        
        return TokenResponse(
            access_token=token_data["access_token"],
            expires_in=expires_in,
            expires_at=expires_at.isoformat()
        )
        
    except Exception as e:
        # Update health state on failure
        health_state["consecutive_failures"] += 1
        
        logger.error(f"❌ Error generating token: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate access token: {str(e)}"
        )

@app.get("/info")
async def api_info():
    """Information about using this API"""
    return {
        "service": "Google Cloud Token Server",
        "version": "1.0.0",
        "usage": {
            "endpoint": "/token",
            "method": "POST", 
            "authentication": "Bearer token in Authorization header (required)",
            "example": "curl -X POST 'https://your-server.com/token' -H 'Authorization: Bearer your-api-key'"
        },
        "token_usage": {
            "description": "Use the returned access token to authenticate Google Cloud Document AI requests",
            "example": "curl -X POST 'https://documentai.googleapis.com/v1/projects/PROJECT/locations/LOCATION/processors/PROCESSOR:process' -H 'Authorization: Bearer ACCESS_TOKEN'"
        },
        "health_endpoints": {
            "basic": "GET / - Basic health check",
            "detailed": "GET /health - Detailed health information", 
            "readiness": "GET /readiness - Readiness probe",
            "liveness": "GET /liveness - Liveness probe"
        }
    }

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    
    # Production-ready uvicorn configuration
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=port,
        log_level="info",
        access_log=True,
        use_colors=False,  # Better for log aggregation
        server_header=False,  # Security
        date_header=False,  # Security
        loop="asyncio",
        http="httptools",
        lifespan="on",
        timeout_keep_alive=65,  # Slightly longer than default load balancer timeout
        timeout_graceful_shutdown=30,  # Time to finish ongoing requests
        limit_concurrency=1000,  # Reasonable limit for token generation
        limit_max_requests=10000,  # Restart worker after this many requests
        backlog=2048
    )
    
    server = uvicorn.Server(config)
    
    try:
        logger.info(f"🚀 Starting Google Cloud Token Server on port {port}")
        server.run()
    except KeyboardInterrupt:
        logger.info("👋 Received shutdown signal, shutting down gracefully...")
    except Exception as e:
        logger.error(f"💥 Server error: {e}")
        raise
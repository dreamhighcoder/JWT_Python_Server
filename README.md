# Google Cloud Token Server

A production-ready FastAPI-based web service that generates short-lived Google Cloud access tokens for Document AI and other Google Cloud services.

## Features

- 🚀 **FastAPI** with automatic API documentation
- 🔐 **API key authentication** for secure access
- 🏥 **Comprehensive health checks** (basic, detailed, readiness, liveness)
- 📊 **Structured logging** with request tracking
- 🔄 **Auto-restart capabilities** with health monitoring
- 🛡️ **Graceful shutdown** handling
- 🚨 **Error tracking** and failure rate monitoring
- 🌐 **CORS support** for web applications
- 🐳 **Docker support** with optimized configuration
- ☁️ **Production-ready** for Cloud Run, Render.com, and other platforms

## Quick Start

### 1. Setup Environment

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your values
# Set your API_KEY and SERVICE_ACCOUNT_JSON
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Run Locally

```bash
python main.py
```

The server will start on `http://localhost:8000`

### Available Endpoints

- **API Documentation**: `http://localhost:8000/docs` (disabled in production)
- **Basic Health Check**: `http://localhost:8000/` - Simple status check
- **Detailed Health**: `http://localhost:8000/health` - Comprehensive health info with stats
- **Readiness Probe**: `http://localhost:8000/readiness` - Kubernetes-style readiness check
- **Liveness Probe**: `http://localhost:8000/liveness` - Kubernetes-style liveness check
- **API Info**: `http://localhost:8000/info` - Service information and usage guide

## Configuration

### Environment Variables

| Variable | Description | Required | Default |
|----------|-------------|----------|---------|
| `API_KEY` | Secret key for API authentication | Yes | - |
| `SERVICE_ACCOUNT_JSON` | Google service account JSON (as string or file path) | Yes | - |
| `PORT` | Server port | No | 8000 |
| `ENVIRONMENT` | Environment type (production, development) | No | development |
| `PYTHONUNBUFFERED` | Disable Python output buffering | No | 0 |

### Service Account Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create or select a project
3. Enable Document AI API
4. Go to IAM & Admin > Service Accounts
5. Create a new service account
6. Grant necessary permissions (Document AI User, etc.)
7. Create and download JSON key
8. Use the JSON content in `SERVICE_ACCOUNT_JSON` environment variable

## Auto-Restart & Monitoring

The application includes built-in monitoring and auto-restart capabilities for production deployments:

### Health Monitoring Features

- **Request Tracking**: Monitors total requests, success rate, and consecutive failures
- **Google Connectivity**: Tests connection to Google's OAuth2 services
- **Failure Detection**: Tracks consecutive failures and degrades service status
- **Graceful Shutdown**: Handles SIGTERM and SIGINT signals properly
- **Uptime Tracking**: Reports service uptime and last successful token generation

### Render.com Auto-Restart

The `render.yaml` configuration includes:
- **Health Check Path**: `/health` endpoint for automatic monitoring
- **Auto Deploy**: Automatically deploys on code changes
- **Resource Limits**: Configured for optimal performance
- **Environment**: Production-ready settings

### Health Check Endpoints

| Endpoint | Purpose | Use Case |
|----------|---------|----------|
| `/` | Basic health | Load balancer health checks |
| `/health` | Detailed status | Monitoring systems, dashboards |
| `/readiness` | Service readiness | Kubernetes readiness probes |
| `/liveness` | Service liveness | Kubernetes liveness probes |

### Sample Health Response

```json
{
  "status": "healthy",
  "service_account_email": "your-service@project.iam.gserviceaccount.com",
  "timestamp": "2024-01-01T12:00:00.000000",
  "uptime_seconds": 3600,
  "stats": {
    "total_requests": 150,
    "successful_requests": 148,
    "consecutive_failures": 0,
    "last_successful_token": "2024-01-01T11:59:30.000000",
    "success_rate": 0.987
  },
  "issues": []
}
```

## API Usage

### Get Access Token

```bash
curl -X POST 'https://your-server.com/token' \
  -H 'Authorization: Bearer your-api-key'
```

Response:
```json
{
  "access_token": "ya29.a0...",
  "token_type": "Bearer",
  "expires_in": 3600,
  "expires_at": "2024-01-01T12:00:00"
}
```

### Use Token with Document AI

```bash
curl -X POST \
  'https://documentai.googleapis.com/v1/projects/PROJECT_ID/locations/us/processors/PROCESSOR_ID:process' \
  -H 'Authorization: Bearer ya29.a0...' \
  -H 'Content-Type: application/json' \
  -d '{
    "rawDocument": {
      "content": "base64-encoded-pdf-content",
      "mimeType": "application/pdf"
    }
  }'
```

## Deployment

### Deploy to Render.com

The project includes a production-ready `render.yaml` configuration:

1. **Connect Repository**: Link your GitHub repository to Render
2. **Auto-Deploy**: The service will auto-deploy using the `render.yaml` configuration
3. **Set Environment Variables** in Render Dashboard:
   - `API_KEY`: Your secret API key (keep this secure!)
   - `SERVICE_ACCOUNT_JSON`: Your complete service account JSON content
4. **Health Monitoring**: Render will automatically monitor `/health` endpoint
5. **Auto-Restart**: Service will restart automatically if health checks fail

**Manual Setup** (if not using render.yaml):
- Build Command: `pip install --upgrade pip && pip install -r requirements.txt`
- Start Command: `python main.py`
- Health Check Path: `/health`

### Deploy to Google Cloud Run

1. **Using Cloud Build (Recommended):**
   ```bash
   gcloud builds submit --config cloudbuild.yaml
   ```

2. **Manual Deployment:**
   ```bash
   # Build and push image
   docker build -t gcr.io/PROJECT_ID/gcp-token-server .
   docker push gcr.io/PROJECT_ID/gcp-token-server
   
   # Deploy to Cloud Run
   gcloud run deploy gcp-token-server \
     --image gcr.io/PROJECT_ID/gcp-token-server \
     --region us-central1 \
     --allow-unauthenticated \
     --set-env-vars API_KEY=your-secret-key,SERVICE_ACCOUNT_JSON='{"type":"service_account",...}'
   ```

### Deploy with Docker

```bash
# Build image
docker build -t gcp-token-server .

# Run container
docker run -p 8000:8000 \
  -e API_KEY=your-secret-key \
  -e SERVICE_ACCOUNT_JSON='{"type":"service_account",...}' \
  gcp-token-server
```

## Security Notes

1. **Change the default API key** in production
2. **Use HTTPS** for all deployments
3. **Restrict service account permissions** to only what's needed
4. **Monitor token usage** and implement rate limiting if needed
5. **Rotate API keys** regularly

## Testing

### Health Checks
```bash
# Basic health check
curl https://your-server.com/

# Detailed health with stats
curl https://your-server.com/health

# Readiness check
curl https://your-server.com/readiness

# Liveness check  
curl https://your-server.com/liveness
```

### Token Generation Test
```bash
curl -X POST 'https://your-server.com/token' \
  -H 'Authorization: Bearer your-api-key'
```

### Service Information
```bash
curl https://your-server.com/info
```

## Production Considerations

### Performance & Scaling

- **Concurrency**: Configured for up to 1000 concurrent requests
- **Worker Restart**: Automatically restarts workers after 10,000 requests
- **Timeout Settings**: Optimized for cloud deployment with 65s keep-alive
- **Memory Usage**: Lightweight design with minimal memory footprint

### Monitoring & Alerting

1. **Set up monitoring** on these endpoints:
   - `/health` - Overall service health
   - `/readiness` - Service readiness
   - `/liveness` - Service availability

2. **Alert on these conditions**:
   - Success rate < 80%
   - Consecutive failures > 5
   - Service status = "unhealthy" or "not_ready"
   - High response times on `/token` endpoint

3. **Key metrics to track**:
   - Request rate and response times
   - Token generation success rate
   - Service uptime
   - Error rates by type

### Logging

- **Structured JSON logs** for production analysis
- **Request tracking** with client IP addresses
- **Error correlation** with detailed stack traces
- **Performance metrics** in log output

### Security Hardening

1. **API Key Management**:
   - Use strong, randomly generated API keys
   - Rotate keys regularly (recommend monthly)
   - Store keys securely (environment variables, not code)

2. **Network Security**:
   - Always use HTTPS in production
   - Consider API rate limiting
   - Implement IP whitelisting if needed

3. **Service Account Security**:
   - Use principle of least privilege
   - Regular permission audits
   - Monitor service account usage

## Troubleshooting

### Common Issues

1. **"Service account credentials not configured properly"**
   - Check that `SERVICE_ACCOUNT_JSON` is set correctly
   - Verify JSON format is valid
   - Ensure file path is correct (if using file path)

2. **"Invalid API key"**
   - Verify `API_KEY` environment variable is set
   - Check Authorization header format: `Bearer your-api-key`

3. **"Failed to obtain access token from Google"**
   - Verify service account has proper permissions
   - Check that Document AI API is enabled in your project
   - Ensure service account JSON is not corrupted

### Logs

The application logs important events:
- Credential loading
- Token generation success/failure  
- API authentication attempts

## License

MIT License
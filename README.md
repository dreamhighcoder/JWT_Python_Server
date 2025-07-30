# Google Cloud Token Server

A FastAPI-based web service that generates short-lived Google Cloud access tokens for Document AI and other Google Cloud services.

## Features

- 🚀 FastAPI with automatic API documentation
- 🔐 API key authentication
- 🏥 Health check endpoints
- 📊 Structured logging
- 🐳 Docker support
- ☁️ Ready for Cloud Run and Render.com deployment

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

- API Documentation: `http://localhost:8000/docs`
- Health Check: `http://localhost:8000/health`

## Configuration

### Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `API_KEY` | Secret key for API authentication | Yes |
| `SERVICE_ACCOUNT_JSON` | Google service account JSON (as string or file path) | Yes |
| `PORT` | Server port (default: 8000) | No |

### Service Account Setup

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create or select a project
3. Enable Document AI API
4. Go to IAM & Admin > Service Accounts
5. Create a new service account
6. Grant necessary permissions (Document AI User, etc.)
7. Create and download JSON key
8. Use the JSON content in `SERVICE_ACCOUNT_JSON` environment variable

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

1. Connect your GitHub repository to Render
2. Create a new Web Service
3. Use the following settings:
   - Build Command: `pip install -r requirements.txt`
   - Start Command: `python main.py`
4. Set environment variables:
   - `API_KEY`: Your secret API key
   - `SERVICE_ACCOUNT_JSON`: Your service account JSON content
   - `PORT`: `10000`

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

### Health Check
```bash
curl https://your-server.com/health
```

### Token Generation Test
```bash
curl -X POST 'https://your-server.com/token' \
  -H 'Authorization: Bearer your-api-key'
```

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
# Faucet Backend Deployment Guide

## Required Environment Variables

For the application to work correctly, you need to set the following environment variables:

- `PRIVATE_KEY`: Your Ethereum wallet private key for signing transactions
- `RPC_URL`: The RPC URL for connecting to the Ethereum network (e.g., Infura endpoint)

## Deployment Steps

1. Ensure you have the following files in your repository:
   - `Dockerfile`
   - `requirements.txt`
   - All the Python source files under the `src/` directory

2. Set up the required environment variables in your deployment platform

3. Build and deploy the Docker container:
   ```bash
   docker build -t faucet-backend .
   docker run -p 10000:10000 --env-file .env faucet-backend
   ```

## Local Development

1. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Create a `.env` file with your environment variables

4. Run the application:
   ```bash
   uvicorn src.main:app --host 0.0.0.0 --port 10000 --reload
   ```
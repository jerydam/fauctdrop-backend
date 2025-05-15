from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from src.config import PRIVATE_KEY, RPC_URL
from src.faucet import claim_tokens, whitelist_user
from src.models import ClaimRequest
from web3 import Web3
import os
from datetime import datetime

app = FastAPI(title="Faucet Backend API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust for production
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

# Initialize Web3
w3 = Web3(Web3.HTTPProvider(RPC_URL))
if not w3.is_connected():
    raise Exception("Failed to connect to Ethereum node")

# Load signer
if not PRIVATE_KEY:
    raise Exception("PRIVATE_KEY not set in environment variables")
signer = w3.eth.account.from_key(PRIVATE_KEY)

@app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

@app.post("/claim")
async def claim(request: ClaimRequest):
    if not w3.is_address(request.userAddress) or not w3.is_address(request.faucetAddress):
        raise HTTPException(status_code=400, detail="Invalid userAddress or faucetAddress")

    try:
        # Whitelist user if requested
        if request.shouldWhitelist:
            try:
                whitelist_tx = await whitelist_user(
                    w3, signer, request.faucetAddress, request.userAddress
                )
                print(f"Whitelisted user {request.userAddress}, tx: {whitelist_tx}")
            except Exception as e:
                print(f"Failed to whitelist user {request.userAddress}: {str(e)}")
                raise HTTPException(status_code=500, detail=f"Failed to whitelist user: {str(e)}")

        # Check if user is whitelisted
        faucet_contract = w3.eth.contract(address=request.faucetAddress, abi=FAUCET_ABI)
        is_whitelisted = await faucet_contract.functions.isWhitelisted(request.userAddress).call()
        if not is_whitelisted:
            print(f"User {request.userAddress} is not whitelisted for faucet {request.faucetAddress}")
            raise HTTPException(status_code=403, detail="User is not whitelisted")

        # Claim tokens
        try:
            tx_hash = await claim_tokens(w3, signer, request.faucetAddress, request.userAddress)
            print(f"Claimed tokens for {request.userAddress}, tx: {tx_hash}")
            return {"success": True, "txHash": tx_hash}
        except Exception as e:
            print(f"Failed to claim tokens for {request.userAddress}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to claim tokens: {str(e)}")
    except Exception as e:
        print(f"Server error for user {request.userAddress}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Server error: {str(e)}")

# Faucet ABI (same as provided in Node.js version)
FAUCET_ABI = [
    # ... (Paste the FAUCET_ABI from your Node.js code here)
    # Note: To keep this concise, I'm not repeating the ABI. Use the same ABI from your original code.
]
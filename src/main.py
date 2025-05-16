from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import traceback
import sys
from src.config import PRIVATE_KEY, RPC_URL
from web3 import Web3
from web3.types import TxReceipt
from eth_account.signers.local import LocalAccount
import asyncio
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

# Define request model
class ClaimRequest(BaseModel):
    userAddress: str
    faucetAddress: str
    shouldWhitelist: bool = True

# Define the FAUCET_ABI here to make it available globally
FAUCET_ABI = [
    {
        "inputs": [],
        "stateMutability": "nonpayable",
        "type": "constructor"
    },
    {
        "inputs": [
            {
                "internalType": "address",
                "name": "owner",
                "type": "address"
            }
        ],
        "name": "OwnableInvalidOwner",
        "type": "error"
    },
    {
        "inputs": [
            {
                "internalType": "address",
                "name": "account",
                "type": "address"
            }
        ],
        "name": "OwnableUnauthorizedAccount",
        "type": "error"
    },
    {
        "anonymous": False,
        "inputs": [
            {
                "indexed": False,
                "internalType": "uint256",
                "name": "claimAmount",
                "type": "uint256"
            },
            {
                "indexed": False,
                "internalType": "uint256",
                "name": "startTime",
                "type": "uint256"
            },
            {
                "indexed": False,
                "internalType": "uint256",
                "name": "endTime",
                "type": "uint256"
            }
        ],
        "name": "ClaimParametersUpdated",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {
                "indexed": True,
                "internalType": "address",
                "name": "user",
                "type": "address"
            },
            {
                "indexed": False,
                "internalType": "uint256",
                "name": "amount",
                "type": "uint256"
            }
        ],
        "name": "Claimed",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {
                "indexed": True,
                "internalType": "address",
                "name": "faucet",
                "type": "address"
            }
        ],
        "name": "FaucetCreated",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {
                "indexed": True,
                "internalType": "address",
                "name": "funder",
                "type": "address"
            },
            {
                "indexed": False,
                "internalType": "uint256",
                "name": "amount",
                "type": "uint256"
            },
            {
                "indexed": False,
                "internalType": "uint256",
                "name": "backendFee",
                "type": "uint256"
            }
        ],
        "name": "Funded",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {
                "indexed": True,
                "internalType": "address",
                "name": "previousOwner",
                "type": "address"
            },
            {
                "indexed": True,
                "internalType": "address",
                "name": "newOwner",
                "type": "address"
            }
        ],
        "name": "OwnershipTransferred",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {
                "indexed": True,
                "internalType": "address",
                "name": "user",
                "type": "address"
            },
            {
                "indexed": False,
                "internalType": "bool",
                "name": "status",
                "type": "bool"
            }
        ],
        "name": "WhitelistUpdated",
        "type": "event"
    },
    {
        "anonymous": False,
        "inputs": [
            {
                "indexed": True,
                "internalType": "address",
                "name": "owner",
                "type": "address"
            },
            {
                "indexed": False,
                "internalType": "uint256",
                "name": "amount",
                "type": "uint256"
            }
        ],
        "name": "Withdrawn",
        "type": "event"
    },
    {
        "inputs": [],
        "name": "BACKEND",
        "outputs": [
            {
                "internalType": "address",
                "name": "",
                "type": "address"
            }
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "BACKEND_FEE_PERCENT",
        "outputs": [
            {
                "internalType": "uint256",
                "name": "",
                "type": "uint256"
            }
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "claim",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "claimAmount",
        "outputs": [
            {
                "internalType": "uint256",
                "name": "",
                "type": "uint256"
            }
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {
                "internalType": "address[]",
                "name": "users",
                "type": "address[]"
            }
        ],
        "name": "claimForBatch",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "endTime",
        "outputs": [
            {
                "internalType": "uint256",
                "name": "",
                "type": "uint256"
            }
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "fund",
        "outputs": [],
        "stateMutability": "payable",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "getFaucetBalance",
        "outputs": [
            {
                "internalType": "uint256",
                "name": "",
                "type": "uint256"
            }
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {
                "internalType": "address",
                "name": "",
                "type": "address"
            }
        ],
        "name": "hasClaimed",
        "outputs": [
            {
                "internalType": "bool",
                "name": "",
                "type": "bool"
            }
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "isClaimActive",
        "outputs": [
            {
                "internalType": "bool",
                "name": "",
                "type": "bool"
            }
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {
                "internalType": "address",
                "name": "",
                "type": "address"
            }
        ],
        "name": "isWhitelisted",
        "outputs": [
            {
                "internalType": "bool",
                "name": "",
                "type": "bool"
            }
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "owner",
        "outputs": [
            {
                "internalType": "address",
                "name": "",
                "type": "address"
            }
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "renounceOwnership",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {
                "internalType": "address[]",
                "name": "users",
                "type": "address[]"
            }
        ],
        "name": "resetClaimed",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {
                "internalType": "uint256",
                "name": "_claimAmount",
                "type": "uint256"
            },
            {
                "internalType": "uint256",
                "name": "_startTime",
                "type": "uint256"
            },
            {
                "internalType": "uint256",
                "name": "_endTime",
                "type": "uint256"
            }
        ],
        "name": "setClaimParameters",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {
                "internalType": "address",
                "name": "user",
                "type": "address"
            },
            {
                "internalType": "bool",
                "name": "status",
                "type": "bool"
            }
        ],
        "name": "setWhitelist",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {
                "internalType": "address[]",
                "name": "users",
                "type": "address[]"
            },
            {
                "internalType": "bool",
                "name": "status",
                "type": "bool"
            }
        ],
        "name": "setWhitelistBatch",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "startTime",
        "outputs": [
            {
                "internalType": "uint256",
                "name": "",
                "type": "uint256"
            }
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [
            {
                "internalType": "address",
                "name": "newOwner",
                "type": "address"
            }
        ],
        "name": "transferOwnership",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {
                "internalType": "uint256",
                "name": "amount",
                "type": "uint256"
            }
        ],
        "name": "withdraw",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "stateMutability": "payable",
        "type": "receive"
    }
]

async def wait_for_transaction_receipt(w3: Web3, tx_hash: str, timeout: int = 120) -> TxReceipt:
    """
    Wait for a transaction receipt with timeout.
    """
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        try:
            receipt = w3.eth.get_transaction_receipt(tx_hash)
            if receipt is not None:
                return receipt
        except Exception:
            pass
        await asyncio.sleep(1)
    raise TimeoutError(f"Transaction {tx_hash} not mined within {timeout} seconds")

async def whitelist_user(
    w3: Web3, 
    signer: LocalAccount, 
    faucet_address: str, 
    user_address: str,
    faucet_abi
) -> str:
    """
    Add a user address to the faucet's whitelist.
    """
    try:
        # Create contract instance
        faucet_contract = w3.eth.contract(address=faucet_address, abi=faucet_abi)
        
        # Check if we need legacy or EIP-1559 transactions
        try:
            # Try to get gas parameters for EIP-1559
            latest_block = w3.eth.get_block('latest')
            supports_eip1559 = 'baseFeePerGas' in latest_block
        except (KeyError, AttributeError):
            supports_eip1559 = False
        
        # Create transaction parameters
        tx_params = {
            'from': signer.address,
            'gas': 200000,  # Set appropriate gas limit
            'nonce': w3.eth.get_transaction_count(signer.address),
        }
        
        # Add appropriate gas price parameters
        if supports_eip1559:
            # EIP-1559 transaction
            base_fee = latest_block['baseFeePerGas'] if isinstance(latest_block, dict) else latest_block.baseFeePerGas
            priority_fee = w3.eth.max_priority_fee
            max_fee_per_gas = int(base_fee * 1.25) + priority_fee
            
            tx_params.update({
                'maxFeePerGas': max_fee_per_gas,
                'maxPriorityFeePerGas': priority_fee,
                'type': 2  # EIP-1559 transaction
            })
        else:
            # Legacy transaction
            tx_params['gasPrice'] = w3.eth.gas_price
        
        # Build transaction for setWhitelist function
        tx = faucet_contract.functions.setWhitelist(
            user_address, 
            True  # Set status to True to whitelist
        ).build_transaction(tx_params)
        
        # Sign the transaction
        signed_tx = signer.sign_transaction(tx)
        
        # Check if we have the raw transaction
        if not hasattr(signed_tx, 'rawTransaction'):
            # Try to handle the case where signed_tx might be a dictionary or have a different structure
            if isinstance(signed_tx, dict) and 'rawTransaction' in signed_tx:
                raw_tx = signed_tx['rawTransaction']
            else:
                # If we can't find rawTransaction, try alternative approaches
                # This might be necessary for some versions of Web3.py
                print(f"WARNING: SignedTransaction object lacks rawTransaction attribute. Type: {type(signed_tx)}")
                print(f"SignedTransaction content: {dir(signed_tx)}")
                
                # Try to extract raw transaction from the signed transaction object
                # This is a fallback approach
                if hasattr(signed_tx, 'raw'):
                    raw_tx = signed_tx.raw
                elif hasattr(signed_tx, 'raw_transaction'):
                    raw_tx = signed_tx.raw_transaction
                else:
                    # If all else fails, use the serialized transaction
                    raw_tx = w3.eth.account.sign_transaction(tx, signer.key).rawTransaction
        else:
            raw_tx = signed_tx.rawTransaction
        
        # Send raw transaction
        tx_hash = w3.eth.send_raw_transaction(raw_tx)
        
        # Wait for transaction confirmation
        receipt = await wait_for_transaction_receipt(w3, tx_hash.hex())
        
        # Check receipt status
        status = receipt['status'] if isinstance(receipt, dict) else receipt.status
        if status != 1:
            raise Exception(f"Transaction failed: {tx_hash.hex()}")
            
        return tx_hash.hex()
    except Exception as e:
        print(f"ERROR in whitelist_user: {str(e)}")
        raise Exception(f"Failed to whitelist user: {str(e)}")

async def claim_tokens(
    w3: Web3, 
    signer: LocalAccount, 
    faucet_address: str, 
    user_address: str,
    faucet_abi
) -> str:
    """
    Claim tokens from the faucet on behalf of a user.
    """
    try:
        # Create contract instance
        faucet_contract = w3.eth.contract(address=faucet_address, abi=faucet_abi)
        
        # Check if we need legacy or EIP-1559 transactions
        try:
            # Try to get gas parameters for EIP-1559
            latest_block = w3.eth.get_block('latest')
            supports_eip1559 = 'baseFeePerGas' in latest_block
        except (KeyError, AttributeError):
            supports_eip1559 = False
        
        # Create transaction parameters
        tx_params = {
            'from': signer.address,
            'gas': 300000,  # Higher gas limit for token transfers
            'nonce': w3.eth.get_transaction_count(signer.address),
        }
        
        # Add appropriate gas price parameters
        if supports_eip1559:
            # EIP-1559 transaction
            base_fee = latest_block['baseFeePerGas'] if isinstance(latest_block, dict) else latest_block.baseFeePerGas
            priority_fee = w3.eth.max_priority_fee
            max_fee_per_gas = int(base_fee * 1.25) + priority_fee
            
            tx_params.update({
                'maxFeePerGas': max_fee_per_gas,
                'maxPriorityFeePerGas': priority_fee,
                'type': 2  # EIP-1559 transaction
            })
        else:
            # Legacy transaction
            tx_params['gasPrice'] = w3.eth.gas_price
        
        # Build transaction for claiming tokens
        tx = faucet_contract.functions.claimForBatch(
            [user_address]  # Pass as a single element array since we're claiming for one user
        ).build_transaction(tx_params)
        
        # Sign the transaction
        signed_tx = signer.sign_transaction(tx)
        
        # Check if we have the raw transaction
        if not hasattr(signed_tx, 'rawTransaction'):
            # Try to handle the case where signed_tx might be a dictionary or have a different structure
            if isinstance(signed_tx, dict) and 'rawTransaction' in signed_tx:
                raw_tx = signed_tx['rawTransaction']
            else:
                # If we can't find rawTransaction, try alternative approaches
                # This might be necessary for some versions of Web3.py
                print(f"WARNING: SignedTransaction object lacks rawTransaction attribute. Type: {type(signed_tx)}")
                print(f"SignedTransaction content: {dir(signed_tx)}")
                
                # Try to extract raw transaction from the signed transaction object
                # This is a fallback approach
                if hasattr(signed_tx, 'raw'):
                    raw_tx = signed_tx.raw
                elif hasattr(signed_tx, 'raw_transaction'):
                    raw_tx = signed_tx.raw_transaction
                else:
                    # If all else fails, use the serialized transaction
                    raw_tx = w3.eth.account.sign_transaction(tx, signer.key).rawTransaction
        else:
            raw_tx = signed_tx.rawTransaction
        
        # Send raw transaction
        tx_hash = w3.eth.send_raw_transaction(raw_tx)
        
        # Wait for transaction confirmation
        receipt = await wait_for_transaction_receipt(w3, tx_hash.hex())
        
        # Check receipt status
        status = receipt['status'] if isinstance(receipt, dict) else receipt.status
        if status != 1:
            raise Exception(f"Transaction failed: {tx_hash.hex()}")
            
        return tx_hash.hex()
    except Exception as e:
        print(f"ERROR in claim_tokens: {str(e)}")
        raise Exception(f"Failed to claim tokens: {str(e)}")

@app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

@app.post("/claim")
async def claim(request: ClaimRequest):
    try:
        print(f"Processing claim request for user {request.userAddress}, faucet {request.faucetAddress}")
        
        # Validate and convert addresses to checksum format
        if not w3.is_address(request.userAddress) or not w3.is_address(request.faucetAddress):
            print(f"Invalid addresses: user={request.userAddress}, faucet={request.faucetAddress}")
            raise HTTPException(status_code=400, detail="Invalid userAddress or faucetAddress")
        
        # Convert to checksum addresses
        user_address = w3.to_checksum_address(request.userAddress)
        faucet_address = w3.to_checksum_address(request.faucetAddress)
        print(f"Converted to checksum addresses: user={user_address}, faucet={faucet_address}")

        # Whitelist user if requested
        if request.shouldWhitelist:
            print(f"Attempting to whitelist user {user_address}")
            try:
                whitelist_tx = await whitelist_user(
                    w3, signer, faucet_address, user_address, FAUCET_ABI
                )
                print(f"Whitelisted user {user_address}, tx: {whitelist_tx}")
            except Exception as e:
                error_msg = f"Failed to whitelist user {user_address}: {str(e)}"
                print(error_msg)
                # Continue with claiming even if whitelisting fails - user might already be whitelisted
                print("Continuing to token claim despite whitelist failure")

        # Check if user is whitelisted
        try:
            faucet_contract = w3.eth.contract(address=faucet_address, abi=FAUCET_ABI)
            is_whitelisted = faucet_contract.functions.isWhitelisted(user_address).call()
            if not is_whitelisted:
                error_msg = f"User {user_address} is not whitelisted for faucet {faucet_address}"
                print(error_msg)
                raise HTTPException(status_code=403, detail="User is not whitelisted")
            print(f"Confirmed user {user_address} is whitelisted")
        except Exception as e:
            error_msg = f"Error checking whitelist status: {str(e)}"
            print(error_msg)
            raise HTTPException(status_code=500, detail=f"Error checking whitelist status: {str(e)}")

        # Claim tokens
        try:
            print(f"Attempting to claim tokens for {user_address}")
            tx_hash = await claim_tokens(w3, signer, faucet_address, user_address, FAUCET_ABI)
            print(f"Claimed tokens for {user_address}, tx: {tx_hash}")
            return {"success": True, "txHash": tx_hash}
        except Exception as e:
            error_msg = f"Failed to claim tokens for {user_address}: {str(e)}"
            print(error_msg)
            raise HTTPException(status_code=500, detail=f"Failed to claim tokens: {str(e)}")
    except ValueError as e:
        # Handle invalid address format errors
        error_msg = f"Invalid address format: {str(e)}"
        print(error_msg)
        raise HTTPException(status_code=400, detail=error_msg)
    except HTTPException as e:
        # Re-raise HTTP exceptions
        raise e
    except Exception as e:
        # Catch all other exceptions
        error_msg = f"Server error for user {request.userAddress}: {str(e)}"
        print(error_msg)
        raise HTTPException(status_code=500, detail=error_msg)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
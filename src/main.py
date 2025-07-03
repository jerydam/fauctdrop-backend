from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from web3 import Web3
from eth_account import Account
from web3.types import TxReceipt
from web3.exceptions import ContractLogicError
import sys
import os
import asyncio
import secrets
from datetime import datetime
from supabase import create_client, Client
from config import PRIVATE_KEY, get_rpc_url

# Add parent directory to sys.path for config import
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

app = FastAPI(title="FaucetDrops Backend API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Adjust for production
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)

# Validate environment variables
if not PRIVATE_KEY:
    raise HTTPException(status_code=500, detail="PRIVATE_KEY not set in environment variables")
if not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_KEY"):
    raise HTTPException(status_code=500, detail="SUPABASE_URL or SUPABASE_KEY not set in environment variables")

# Initialize Supabase client
supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))

# FAUCET_ABI
FAUCET_ABI = [
	{
		"inputs": [
			{
				"internalType": "string",
				"name": "_name",
				"type": "string"
			},
			{
				"internalType": "address",
				"name": "_token",
				"type": "address"
			},
			{
				"internalType": "address",
				"name": "_backend",
				"type": "address"
			},
			{
				"internalType": "address",
				"name": "_owner",
				"type": "address"
			},
			{
				"internalType": "address",
				"name": "_factory",
				"type": "address"
			}
		],
		"stateMutability": "nonpayable",
		"type": "constructor"
	},
	{
		"inputs": [],
		"name": "AlreadyClaimed",
		"type": "error"
	},
	{
		"inputs": [],
		"name": "ArrayLengthMismatch",
		"type": "error"
	},
	{
		"inputs": [],
		"name": "ClaimAmountNotSet",
		"type": "error"
	},
	{
		"inputs": [],
		"name": "ClaimPeriodEnded",
		"type": "error"
	},
	{
		"inputs": [],
		"name": "ClaimPeriodNotStarted",
		"type": "error"
	},
	{
		"inputs": [],
		"name": "ContractPaused",
		"type": "error"
	},
	{
		"inputs": [],
		"name": "EmptyName",
		"type": "error"
	},
	{
		"inputs": [],
		"name": "InsufficientBalance",
		"type": "error"
	},
	{
		"inputs": [],
		"name": "InvalidAddress",
		"type": "error"
	},
	{
		"inputs": [],
		"name": "InvalidAmount",
		"type": "error"
	},
	{
		"inputs": [],
		"name": "InvalidTime",
		"type": "error"
	},
	{
		"inputs": [],
		"name": "NoUsersProvided",
		"type": "error"
	},
	{
		"inputs": [],
		"name": "NotWhitelisted",
		"type": "error"
	},
	{
		"inputs": [],
		"name": "OnlyAdmin",
		"type": "error"
	},
	{
		"inputs": [],
		"name": "OnlyBackend",
		"type": "error"
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
		"inputs": [],
		"name": "ReentrancyGuardReentrantCall",
		"type": "error"
	},
	{
		"inputs": [],
		"name": "TransferFailed",
		"type": "error"
	},
	{
		"anonymous": False,
		"inputs": [
			{
				"indexed": True,
				"internalType": "address",
				"name": "admin",
				"type": "address"
			}
		],
		"name": "AdminAdded",
		"type": "event"
	},
	{
		"anonymous": False,
		"inputs": [
			{
				"indexed": True,
				"internalType": "address",
				"name": "newBackend",
				"type": "address"
			}
		],
		"name": "BackendUpdated",
		"type": "event"
	},
	{
		"anonymous": False,
		"inputs": [
			{
				"indexed": False,
				"internalType": "uint256",
				"name": "userCount",
				"type": "uint256"
			}
		],
		"name": "BatchClaimReset",
		"type": "event"
	},
	{
		"anonymous": False,
		"inputs": [
			{
				"indexed": False,
				"internalType": "uint256",
				"name": "userCount",
				"type": "uint256"
			}
		],
		"name": "BatchCustomClaimAmountsSet",
		"type": "event"
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
			}
		],
		"name": "ClaimReset",
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
			},
			{
				"indexed": False,
				"internalType": "bool",
				"name": "isEther",
				"type": "bool"
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
				"name": "user",
				"type": "address"
			}
		],
		"name": "CustomClaimAmountRemoved",
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
		"name": "CustomClaimAmountSet",
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
			},
			{
				"indexed": False,
				"internalType": "string",
				"name": "name",
				"type": "string"
			},
			{
				"indexed": False,
				"internalType": "address",
				"name": "token",
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
				"name": "faucet",
				"type": "address"
			}
		],
		"name": "FaucetDeleted",
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
			},
			{
				"indexed": False,
				"internalType": "bool",
				"name": "isEther",
				"type": "bool"
			}
		],
		"name": "Funded",
		"type": "event"
	},
	{
		"anonymous": False,
		"inputs": [
			{
				"indexed": False,
				"internalType": "string",
				"name": "newName",
				"type": "string"
			}
		],
		"name": "NameUpdated",
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
				"indexed": False,
				"internalType": "bool",
				"name": "paused",
				"type": "bool"
			}
		],
		"name": "Paused",
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
			},
			{
				"indexed": False,
				"internalType": "bool",
				"name": "isEther",
				"type": "bool"
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
		"inputs": [
			{
				"internalType": "address",
				"name": "_admin",
				"type": "address"
			}
		],
		"name": "addAdmin",
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
		"name": "claimWhenActive",
		"outputs": [],
		"stateMutability": "nonpayable",
		"type": "function"
	},
	{
		"inputs": [
			{
				"internalType": "uint256",
				"name": "",
				"type": "uint256"
			}
		],
		"name": "claims",
		"outputs": [
			{
				"internalType": "address",
				"name": "recipient",
				"type": "address"
			},
			{
				"internalType": "uint256",
				"name": "amount",
				"type": "uint256"
			},
			{
				"internalType": "uint256",
				"name": "timestamp",
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
		"name": "customClaimAmounts",
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
		"name": "deleteFaucet",
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
		"name": "factory",
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
		"inputs": [
			{
				"internalType": "uint256",
				"name": "_tokenAmount",
				"type": "uint256"
			}
		],
		"name": "fund",
		"outputs": [],
		"stateMutability": "payable",
		"type": "function"
	},
	{
		"inputs": [
			{
				"internalType": "address",
				"name": "_address",
				"type": "address"
			}
		],
		"name": "getAdminStatus",
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
		"name": "getAllClaims",
		"outputs": [
			{
				"components": [
					{
						"internalType": "address",
						"name": "recipient",
						"type": "address"
					},
					{
						"internalType": "uint256",
						"name": "amount",
						"type": "uint256"
					},
					{
						"internalType": "uint256",
						"name": "timestamp",
						"type": "uint256"
					}
				],
				"internalType": "struct FaucetDrops.ClaimDetail[]",
				"name": "",
				"type": "tuple[]"
			}
		],
		"stateMutability": "view",
		"type": "function"
	},
	{
		"inputs": [
			{
				"internalType": "address",
				"name": "user",
				"type": "address"
			}
		],
		"name": "getClaimStatus",
		"outputs": [
			{
				"internalType": "bool",
				"name": "claimed",
				"type": "bool"
			},
			{
				"internalType": "bool",
				"name": "whitelisted",
				"type": "bool"
			},
			{
				"internalType": "bool",
				"name": "canClaim",
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
				"name": "user",
				"type": "address"
			}
		],
		"name": "getCustomClaimAmount",
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
				"name": "user",
				"type": "address"
			}
		],
		"name": "getDetailedClaimStatus",
		"outputs": [
			{
				"internalType": "bool",
				"name": "claimed",
				"type": "bool"
			},
			{
				"internalType": "bool",
				"name": "whitelisted",
				"type": "bool"
			},
			{
				"internalType": "bool",
				"name": "canClaim",
				"type": "bool"
			},
			{
				"internalType": "uint256",
				"name": "claimAmountForUser",
				"type": "uint256"
			},
			{
				"internalType": "bool",
				"name": "hasCustom",
				"type": "bool"
			}
		],
		"stateMutability": "view",
		"type": "function"
	},
	{
		"inputs": [],
		"name": "getFaucetBalance",
		"outputs": [
			{
				"internalType": "uint256",
				"name": "balance",
				"type": "uint256"
			},
			{
				"internalType": "bool",
				"name": "isEther",
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
				"name": "user",
				"type": "address"
			}
		],
		"name": "getUserClaimAmount",
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
		"inputs": [
			{
				"internalType": "address",
				"name": "",
				"type": "address"
			}
		],
		"name": "hasCustomAmount",
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
		"name": "isAdmin",
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
		"name": "name",
		"outputs": [
			{
				"internalType": "string",
				"name": "",
				"type": "string"
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
		"name": "paused",
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
		"name": "renounceOwnership",
		"outputs": [],
		"stateMutability": "nonpayable",
		"type": "function"
	},
	{
		"inputs": [],
		"name": "resetAllClaimed",
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
		"name": "resetClaimedBatch",
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
			}
		],
		"name": "resetClaimedSingle",
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
				"internalType": "uint256",
				"name": "amount",
				"type": "uint256"
			}
		],
		"name": "setCustomClaimAmount",
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
				"internalType": "uint256[]",
				"name": "amounts",
				"type": "uint256[]"
			}
		],
		"name": "setCustomClaimAmountsBatch",
		"outputs": [],
		"stateMutability": "nonpayable",
		"type": "function"
	},
	{
		"inputs": [
			{
				"internalType": "bool",
				"name": "_paused",
				"type": "bool"
			}
		],
		"name": "setPaused",
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
		"inputs": [],
		"name": "token",
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
				"internalType": "string",
				"name": "_newName",
				"type": "string"
			}
		],
		"name": "updateName",
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
			}
		],
		"name": "userHasCustomAmount",
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

# Initialize signer globally
signer = Account.from_key(PRIVATE_KEY)

async def get_web3_instance(chain_id: int) -> Web3:
    try:
        rpc_url = get_rpc_url(chain_id)
        if not rpc_url:
            raise HTTPException(status_code=400, detail=f"No RPC URL configured for chain {chain_id}")
        
        w3 = Web3(Web3.HTTPProvider(rpc_url))
        if not w3.is_connected():
            raise HTTPException(status_code=500, detail=f"Failed to connect to node for chain {chain_id}: {rpc_url}")
        
        return w3
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to initialize Web3 for chain {chain_id}: {str(e)}")

async def wait_for_transaction_receipt(w3: Web3, tx_hash: str, timeout: int = 300) -> TxReceipt:
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        try:
            receipt = w3.eth.get_transaction_receipt(tx_hash)
            if receipt is not None:
                return receipt
        except Exception:
            pass
        await asyncio.sleep(2)
    raise HTTPException(status_code=500, detail=f"Transaction {tx_hash} not mined within {timeout} seconds")

async def check_whitelist_status(w3: Web3, faucet_address: str, user_address: str) -> bool:
    faucet_contract = w3.eth.contract(address=faucet_address, abi=FAUCET_ABI)
    for _ in range(5):
        try:
            return faucet_contract.functions.isWhitelisted(user_address).call()
        except (ContractLogicError, ValueError) as e:
            print(f"Retry checking whitelist status: {str(e)}")
            await asyncio.sleep(2)
    raise HTTPException(status_code=500, detail="Failed to check whitelist status after retries")

async def check_pause_status(w3: Web3, faucet_address: str) -> bool:
    faucet_contract = w3.eth.contract(address=faucet_address, abi=FAUCET_ABI)
    try:
        return faucet_contract.functions.paused().call()
    except (ContractLogicError, ValueError) as e:
        print(f"Error checking pause status: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to check pause status")

async def whitelist_user(w3: Web3, faucet_address: str, user_address: str) -> str:
    try:
        faucet_contract = w3.eth.contract(address=faucet_address, abi=FAUCET_ABI)
        supports_eip1559 = False
        try:
            latest_block = w3.eth.get_block('latest')
            supports_eip1559 = 'baseFeePerGas' in latest_block
        except (KeyError, AttributeError):
            pass
        
        tx_params = {
            'from': signer.address,
            'gas': 200000,
            'nonce': w3.eth.get_transaction_count(signer.address),
            'chainId': w3.eth.chain_id
        }
        
        if supports_eip1559:
            base_fee = latest_block.get('baseFeePerGas', 0)
            priority_fee = w3.eth.max_priority_fee
            max_fee_per_gas = int(base_fee * 1.25) + priority_fee
            tx_params.update({
                'maxFeePerGas': max_fee_per_gas,
                'maxPriorityFeePerGas': priority_fee,
                'type': 2
            })
        else:
            tx_params['gasPrice'] = w3.eth.gas_price
        
        balance = w3.eth.get_balance(signer.address)
        if balance < 6250200000000000:
            raise HTTPException(status_code=400, detail=f"Insufficient funds in signer account {signer.address}: balance {w3.from_wei(balance, 'ether')} CELO, required ~0.00625 CELO")
        
        tx = faucet_contract.functions.setWhitelist(user_address, True).build_transaction(tx_params)
        signed_tx = w3.eth.account.sign_transaction(tx, signer.key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = await wait_for_transaction_receipt(w3, tx_hash.hex())
        
        if receipt.get('status', 0) != 1:
            raise HTTPException(status_code=400, detail=f"Transaction failed: {tx_hash.hex()}")
        return tx_hash.hex()
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"ERROR in whitelist_user: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

async def generate_secret_code() -> str:
    """Generate a 6-character alphanumeric secret code."""
    characters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    return ''.join(secrets.choice(characters) for _ in range(6))

async def store_secret_code(faucet_address: str, secret_code: str, start_time: int, end_time: int):
    """Store the secret code in Supabase."""
    try:
        data = {
            "faucet_address": faucet_address,
            "secret_code": secret_code,
            "start_time": start_time,
            "end_time": end_time
        }
        response = supabase.table("secret_codes").upsert(data, on_conflict="faucet_address").execute()
        if not response.data:
            raise HTTPException(status_code=500, detail="Failed to store secret code in Supabase")
    except Exception as e:
        print(f"Supabase error in store_secret_code: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Supabase error: {str(e)}")

async def verify_secret_code(faucet_address: str, secret_code: str) -> bool:
    """Verify the secret code against Supabase."""
    try:
        response = supabase.table("secret_codes").select("*").eq("faucet_address", faucet_address).execute()
        if not response.data or len(response.data) == 0:
            return False
        record = response.data[0]
        current_time = int(datetime.now().timestamp())
        return (
            record["secret_code"] == secret_code
            and record["start_time"] <= current_time <= record["end_time"]
        )
    except Exception as e:
        print(f"Supabase error in verify_secret_code: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Supabase error: {str(e)}")

async def set_claim_parameters(faucet_address: str, start_time: int, end_time: int) -> str:
    try:
        secret_code = await generate_secret_code()
        await store_secret_code(faucet_address, secret_code, start_time, end_time)
        print(f"Generated secret code for {faucet_address}: {secret_code}")
        return secret_code
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"ERROR in set_claim_parameters: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate secret code: {str(e)}")

async def claim_tokens(w3: Web3, faucet_address: str, user_address: str, secret_code: str) -> str:
    try:
        is_valid_code = await verify_secret_code(faucet_address, secret_code)
        if not is_valid_code:
            raise HTTPException(status_code=403, detail="Invalid or expired secret code")

        # Check if contract is paused
        is_paused = await check_pause_status(w3, faucet_address)
        if is_paused:
            raise HTTPException(status_code=400, detail="Faucet is paused")

        faucet_contract = w3.eth.contract(address=faucet_address, abi=FAUCET_ABI)
        
        supports_eip1559 = False
        try:
            latest_block = w3.eth.get_block('latest')
            supports_eip1559 = 'baseFeePerGas' in latest_block
        except (KeyError, AttributeError):
            pass
        
        tx_params = {
            'from': signer.address,
            'chainId': w3.eth.chain_id,
            'nonce': w3.eth.get_transaction_count(signer.address, 'pending'),
        }
        
        tx = faucet_contract.functions.claim([user_address]).build_transaction(tx_params)
        tx_params['gas'] = w3.eth.estimate_gas(tx)
        
        if supports_eip1559:
            base_fee = latest_block.get('baseFeePerGas', 0)
            priority_fee = w3.eth.max_priority_fee
            max_fee_per_gas = int(base_fee * 1.25) + priority_fee
            tx_params.update({
                'maxFeePerGas': max_fee_per_gas,
                'maxPriorityFeePerGas': priority_fee,
                'type': 2
            })
        else:
            tx_params['gasPrice'] = w3.eth.gas_price
        
        balance = w3.eth.get_balance(signer.address)
        if balance < 6250200000000000:
            raise HTTPException(status_code=400, detail=f"Insufficient funds in signer account {signer.address}: balance {w3.from_wei(balance, 'ether')} CELO, required ~0.00625 CELO")
        
        signed_tx = w3.eth.account.sign_transaction(tx, signer.key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = await wait_for_transaction_receipt(w3, tx_hash.hex())
        
        if receipt.get('status', 0) != 1:
            try:
                w3.eth.call(tx, block_identifier=receipt['blockNumber'])
            except Exception as revert_error:
                raise HTTPException(status_code=400, detail=f"Claim failed: {str(revert_error)}")
        
        return tx_hash.hex()
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"ERROR in claim_tokens: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to claim tokens: {str(e)}")

async def claim_tokens_no_code(w3: Web3, faucet_address: str, user_address: str) -> str:
    """Claim tokens without requiring a secret code."""
    try:
        # Check if contract is paused
        is_paused = await check_pause_status(w3, faucet_address)
        if is_paused:
            raise HTTPException(status_code=400, detail="Faucet is paused")

        faucet_contract = w3.eth.contract(address=faucet_address, abi=FAUCET_ABI)
        
        supports_eip1559 = False
        try:
            latest_block = w3.eth.get_block('latest')
            supports_eip1559 = 'baseFeePerGas' in latest_block
        except (KeyError, AttributeError):
            pass
        
        tx_params = {
            'from': signer.address,
            'chainId': w3.eth.chain_id,
            'nonce': w3.eth.get_transaction_count(signer.address, 'pending'),
        }
        
        tx = faucet_contract.functions.claim([user_address]).build_transaction(tx_params)
        tx_params['gas'] = w3.eth.estimate_gas(tx)
        
        if supports_eip1559:
            base_fee = latest_block.get('baseFeePerGas', 0)
            priority_fee = w3.eth.max_priority_fee
            max_fee_per_gas = int(base_fee * 1.25) + priority_fee
            tx_params.update({
                'maxFeePerGas': max_fee_per_gas,
                'maxPriorityFeePerGas': priority_fee,
                'type': 2
            })
        else:
            tx_params['gasPrice'] = w3.eth.gas_price
        
        balance = w3.eth.get_balance(signer.address)
        if balance < 6250200000000000:
            raise HTTPException(status_code=400, detail=f"Insufficient funds in signer account {signer.address}: balance {w3.from_wei(balance, 'ether')} CELO, required ~0.00625 CELO")
        
        signed_tx = w3.eth.account.sign_transaction(tx, signer.key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = await wait_for_transaction_receipt(w3, tx_hash.hex())
        
        if receipt.get('status', 0) != 1:
            try:
                w3.eth.call(tx, block_identifier=receipt['blockNumber'])
            except Exception as revert_error:
                raise HTTPException(status_code=400, detail=f"Claim failed: {str(revert_error)}")
        
        return tx_hash.hex()
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"ERROR in claim_tokens_no_code: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to claim tokens: {str(e)}")

class ClaimRequest(BaseModel):
    userAddress: str
    faucetAddress: str
    secretCode: str
    shouldWhitelist: bool = True
    chainId: int

class ClaimNoCodeRequest(BaseModel):
    userAddress: str
    faucetAddress: str
    shouldWhitelist: bool = True
    chainId: int

class SetClaimParametersRequest(BaseModel):
    faucetAddress: str
    claimAmount: int
    startTime: int
    endTime: int
    chainId: int

class GetSecretCodeRequest(BaseModel):
    faucetAddress: str

@app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

@app.post("/set-claim-parameters")
async def set_claim_parameters_endpoint(request: SetClaimParametersRequest):
    try:
        print(f"Received set claim parameters request: {request.dict()}")
        
        if not Web3.is_address(request.faucetAddress):
            raise HTTPException(status_code=400, detail=f"Invalid faucetAddress: {request.faucetAddress}")
        
        valid_chain_ids = [1135, 42220, 42161]
        if request.chainId not in valid_chain_ids:
            raise HTTPException(status_code=400, detail=f"Invalid chainId: {request.chainId}. Must be one of {valid_chain_ids}")
        
        faucet_address = Web3.to_checksum_address(request.faucetAddress)
        
        secret_code = await set_claim_parameters(faucet_address, request.startTime, request.endTime)
        print(f"Generated secret code for {faucet_address}: {secret_code}")
        return {"success": True, "secretCode": secret_code}
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Server error in set_claim_parameters: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/claim")
async def claim(request: ClaimRequest):
    try:
        print(f"Received claim request: {request.dict()}")
        
        w3 = await get_web3_instance(request.chainId)
        
        try:
            user_address = w3.to_checksum_address(request.userAddress)
            faucet_address = w3.to_checksum_address(request.faucetAddress)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid address: {str(e)}")
        
        if request.chainId not in [1135, 42220, 42161]:
            raise HTTPException(status_code=400, detail=f"Invalid chainId: {request.chainId}. Must be one of [1135, 42220, 42161]")
        
        print(f"Converted to checksum addresses: user={user_address}, faucet={faucet_address}")

        faucet_contract = w3.eth.contract(address=faucet_address, abi=FAUCET_ABI)
        balance = w3.eth.get_balance(faucet_address)
        backend = faucet_contract.functions.BACKEND().call()
        backend_fee_percent = faucet_contract.functions.BACKEND_FEE_PERCENT().call()
        native_currency = "CELO" if request.chainId == 42220 else "LISK" if request.chainId == 1135 else "ETH"
        print(f"Faucet details: balance={w3.from_wei(balance, 'ether')} {native_currency}, BACKEND={backend}, BACKEND_FEE_PERCENT={backend_fee_percent}%")

        if not Web3.is_address(backend):
            raise HTTPException(status_code=500, detail="Invalid BACKEND address in contract")

        whitelist_tx = None
        if request.shouldWhitelist:
            try:
                whitelist_tx = await whitelist_user(w3, faucet_address, user_address)
                print(f"Whitelisted user {user_address}, tx: {whitelist_tx}")
            except HTTPException as e:
                raise e
            except Exception as e:
                print(f"Failed to whitelist user {user_address}: {str(e)}")

        is_whitelisted = await check_whitelist_status(w3, faucet_address, user_address)
        if not is_whitelisted:
            raise HTTPException(status_code=403, detail="User is not whitelisted")
        print(f"Confirmed user {user_address} is whitelisted")

        tx_hash = await claim_tokens(w3, faucet_address, user_address, request.secretCode)
        print(f"Claimed tokens for {user_address}, tx: {tx_hash}")
        return {"success": True, "txHash": tx_hash, "whitelistTx": whitelist_tx}
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Server error for user {request.userAddress}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/claim-no-code")
async def claim_no_code(request: ClaimNoCodeRequest):
    """Endpoint to claim tokens without requiring a secret code."""
    try:
        print(f"Received claim-no-code request: {request.dict()}")
        
        w3 = await get_web3_instance(request.chainId)
        
        try:
            user_address = w3.to_checksum_address(request.userAddress)
            faucet_address = w3.to_checksum_address(request.faucetAddress)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid address: {str(e)}")
        
        if request.chainId not in [1135, 42220, 42161]:
            raise HTTPException(status_code=400, detail=f"Invalid chainId: {request.chainId}. Must be one of [1135, 42220, 42161]")
        
        print(f"Converted to checksum addresses: user={user_address}, faucet={faucet_address}")

        faucet_contract = w3.eth.contract(address=faucet_address, abi=FAUCET_ABI)
        balance = w3.eth.get_balance(faucet_address)
        backend = faucet_contract.functions.BACKEND().call()
        backend_fee_percent = faucet_contract.functions.BACKEND_FEE_PERCENT().call()
        native_currency = "CELO" if request.chainId == 42220 else "LISK" if request.chainId == 1135 else "ETH"
        print(f"Faucet details: balance={w3.from_wei(balance, 'ether')} {native_currency}, BACKEND={backend}, BACKEND_FEE_PERCENT={backend_fee_percent}%")

        if not Web3.is_address(backend):
            raise HTTPException(status_code=500, detail="Invalid BACKEND address in contract")

    

        tx_hash = await claim_tokens_no_code(w3, faucet_address, user_address)
        print(f"Claimed tokens for {user_address}, tx: {tx_hash}")
        return {"success": True, "txHash": tx_hash}
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Server error for user {request.userAddress}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/secret-codes")
async def get_secret_codes():
    try:
        response = supabase.table("secret_codes").select("*").execute()
        if not response.data:
            return []
        return [
            {
                "faucetAddress": row["faucet_address"],
                "secretCode": row["secret_code"],
                "startTime": row["start_time"],
                "endTime": row["end_time"],
                "createdAt": row["created_at"]
            }
            for row in response.data
        ]
    except Exception as e:
        print(f"Supabase error in get_secret_codes: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Supabase error: {str(e)}")

@app.get("/get-secret-code")
async def get_secret_code(request: GetSecretCodeRequest):
    try:
        if not Web3.is_address(request.faucetAddress):
            raise HTTPException(status_code=400, detail=f"Invalid faucetAddress: {request.faucetAddress}")
        
        faucet_address = Web3.to_checksum_address(request.faucetAddress)
        
        response = supabase.table("secret_codes").select("*").eq("faucet_address", faucet_address).execute()
        if not response.data or len(response.data) == 0:
            raise HTTPException(status_code=404, detail=f"No secret code found for faucet address: {faucet_address}")
        
        record = response.data[0]
        current_time = int(datetime.now().timestamp())
        is_valid = record["start_time"] <= current_time <= record["end_time"]
        
        return {
            "faucetAddress": faucet_address,
            "secretCode": record["secret_code"],
            "startTime": record["start_time"],
            "endTime": record["end_time"],
            "isValid": is_valid,
            "createdAt": record["created_at"]
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Error in get_secret_code: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve secret code: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=10000)
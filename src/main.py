from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from web3 import Web3
from typing import Dict, Tuple
from eth_account import Account
from web3.types import TxReceipt
from web3.exceptions import ContractLogicError
import sys
import os
import asyncio
import secrets
from datetime import datetime
from typing import Optional, Dict, Any
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

# FAUCET_ABI (keeping the same ABI)
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

# Pydantic Models
class ClaimRequest(BaseModel):
    userAddress: str
    faucetAddress: str
    secretCode: str
    shouldWhitelist: bool = True
    chainId: int
    divviReferralData: Optional[str] = None

class ClaimNoCodeRequest(BaseModel):
    userAddress: str
    faucetAddress: str
    shouldWhitelist: bool = True
    chainId: int
    divviReferralData: Optional[str] = None

class ClaimCustomRequest(BaseModel):
    userAddress: str
    faucetAddress: str
    chainId: int
    divviReferralData: Optional[str] = None

class SetClaimParametersRequest(BaseModel):
    faucetAddress: str
    claimAmount: int
    startTime: int
    endTime: int
    chainId: int

class GetSecretCodeRequest(BaseModel):
    faucetAddress: str
    
class AdminPopupPreferenceRequest(BaseModel):
    userAddress: str
    faucetAddress: str
    dontShowAgain: bool

class GetAdminPopupPreferenceRequest(BaseModel):
    userAddress: str
    faucetAddress: str
    
    
# SIMPLIFIED GAS CONFIGURATION - Just chain names for reference
CHAIN_INFO = {
    42220: {"name": "Celo Mainnet", "native_token": "CELO"},
    44787: {"name": "Celo Testnet", "native_token": "CELO"},
    42161: {"name": "Arbitrum One", "native_token": "ETH"},
    421614: {"name": "Arbitrum Testnet", "native_token": "ETH"},
    1135: {"name": "Lisk", "native_token": "LISK"},
    4202: {"name": "Lisk Testnet", "native_token": "LISK"},
    8453: {"name": "Base", "native_token": "ETH"},
    84532: {"name": "Base Testnet", "native_token": "ETH"},
}

def get_chain_info(chain_id: int) -> Dict:
    """Get basic chain information."""
    return CHAIN_INFO.get(chain_id, {"name": "Unknown Network", "native_token": "ETH"})

def check_sufficient_balance(w3: Web3, signer_address: str, min_balance_eth: float = 0.000001) -> Tuple[bool, str]:
    """
    Simplified balance check - just ensure we have some minimum balance for gas.
    
    Args:
        w3: Web3 instance
        signer_address: Signer wallet address
        min_balance_eth: Minimum balance in ETH/native tokens (default 0.001)
        
    Returns:
        Tuple of (is_sufficient, error_message)
    """
    try:
        balance = w3.eth.get_balance(signer_address)
        min_balance_wei = w3.to_wei(min_balance_eth, 'ether')
        chain_info = get_chain_info(w3.eth.chain_id)
        
        if balance < min_balance_wei:
            balance_formatted = w3.from_wei(balance, 'ether')
            
            error_msg = (
                f"Insufficient funds: balance {balance_formatted} {chain_info['native_token']}, "
                f"minimum required ~{min_balance_eth} {chain_info['native_token']}"
            )
            return False, error_msg
        
        return True, ""
        
    except Exception as e:
        return False, f"Error checking balance: {str(e)}"

def build_transaction_with_standard_gas(w3: Web3, contract_function, from_address: str) -> dict:
    """
    Build transaction using standard network gas pricing - no custom logic.
    
    Args:
        w3: Web3 instance
        contract_function: Contract function to call
        from_address: Sender address
        
    Returns:
        Transaction dictionary with standard gas settings
    """
    try:
        # Get current network gas price
        gas_price = w3.eth.gas_price
        
        # Build base transaction
        tx_params = {
            'from': from_address,
            'chainId': w3.eth.chain_id,
            'nonce': w3.eth.get_transaction_count(from_address, 'pending'),
            'gasPrice': gas_price  # Use network standard gas price
        }
        
        # Build transaction
        tx = contract_function.build_transaction(tx_params)
        
        # Let Web3 estimate gas naturally
        try:
            estimated_gas = w3.eth.estimate_gas(tx)
            # Add small buffer (10%) to be safe
            tx['gas'] = int(estimated_gas * 1.1)
        except Exception as e:
            print(f"⚠️ Gas estimation failed: {str(e)}, using default")
            # Fallback to a reasonable default
            tx['gas'] = 200000
        
        chain_info = get_chain_info(w3.eth.chain_id)
        print(f"⛽ Standard gas on {chain_info['name']}: {tx['gas']} gas @ {gas_price} wei")
        
        return tx
        
    except Exception as e:
        print(f"❌ Error building transaction: {str(e)}")
        raise

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
        chain_info = get_chain_info(w3.eth.chain_id)
        
        faucet_contract = w3.eth.contract(address=faucet_address, abi=FAUCET_ABI)
        
        # Check balance with simplified requirements
        balance_ok, balance_error = check_sufficient_balance(w3, signer.address)
        if not balance_ok:
            raise HTTPException(status_code=400, detail=balance_error)
        
        # Build transaction with standard gas
        tx = build_transaction_with_standard_gas(
            w3, 
            faucet_contract.functions.setWhitelist(user_address, True), 
            signer.address
        )
        
        # Sign and send
        signed_tx = w3.eth.account.sign_transaction(tx, signer.key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = await wait_for_transaction_receipt(w3, tx_hash.hex())
        
        if receipt.get('status', 0) != 1:
            raise HTTPException(status_code=400, detail=f"Whitelist transaction failed: {tx_hash.hex()}")
        
        print(f"✅ Whitelist successful on {chain_info['name']}: {tx_hash.hex()}")
        return tx_hash.hex()
        
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"ERROR in whitelist_user: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
    
    # Enhanced Secret Code Database Functions
async def get_secret_code_from_db(faucet_address: str) -> Optional[Dict[str, Any]]:
    """
    Get secret code from database for a specific faucet address.
    
    Args:
        faucet_address: The faucet contract address
        
    Returns:
        Dictionary with secret code data or None if not found
        
    Raises:
        HTTPException: If database error occurs
    """
    try:
        if not Web3.is_address(faucet_address):
            raise HTTPException(status_code=400, detail=f"Invalid faucet address: {faucet_address}")
        
        # Convert to checksum address for consistency
        checksum_address = Web3.to_checksum_address(faucet_address)
        
        response = supabase.table("secret_codes").select("*").eq("faucet_address", checksum_address).execute()
        
        if not response.data or len(response.data) == 0:
            return None
        
        record = response.data[0]
        current_time = int(datetime.now().timestamp())
        
        return {
            "faucet_address": record["faucet_address"],
            "secret_code": record["secret_code"],
            "start_time": record["start_time"],
            "end_time": record["end_time"],
            "is_valid": record["start_time"] <= current_time <= record["end_time"],
            "is_expired": current_time > record["end_time"],
            "is_future": current_time < record["start_time"],
            "created_at": record.get("created_at"),
            "time_remaining": max(0, record["end_time"] - current_time) if current_time <= record["end_time"] else 0
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Database error in get_secret_code_from_db: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

async def get_valid_secret_code(faucet_address: str) -> Optional[str]:
    """
    Get only the secret code string if it's currently valid.
    
    Args:
        faucet_address: The faucet contract address
        
    Returns:
        Secret code string if valid, None otherwise
    """
    try:
        code_data = await get_secret_code_from_db(faucet_address)
        
        if code_data and code_data["is_valid"]:
            return code_data["secret_code"]
            
        return None
        
    except Exception as e:
        print(f"Error getting valid secret code: {str(e)}")
        return None

async def get_all_secret_codes() -> list:
    """
    Get all secret codes from database with their validity status.
    
    Returns:
        List of all secret codes with metadata
    """
    try:
        response = supabase.table("secret_codes").select("*").order("created_at", desc=True).execute()
        
        if not response.data:
            return []
        
        current_time = int(datetime.now().timestamp())
        codes = []
        
        for row in response.data:
            codes.append({
                "faucet_address": row["faucet_address"],
                "secret_code": row["secret_code"],
                "start_time": row["start_time"],
                "end_time": row["end_time"],
                "is_valid": row["start_time"] <= current_time <= row["end_time"],
                "is_expired": current_time > row["end_time"],
                "is_future": current_time < row["start_time"],
                "created_at": row.get("created_at"),
                "time_remaining": max(0, row["end_time"] - current_time) if current_time <= row["end_time"] else 0
            })
        
        return codes
        
    except Exception as e:
        print(f"Database error in get_all_secret_codes: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

async def check_secret_code_status(faucet_address: str, secret_code: str) -> Dict[str, Any]:
    """
    Check if a provided secret code matches and is valid for a faucet.
    
    Args:
        faucet_address: The faucet contract address
        secret_code: The secret code to verify
        
    Returns:
        Dictionary with validation results
    """
    try:
        code_data = await get_secret_code_from_db(faucet_address)
        
        if not code_data:
            return {
                "valid": False,
                "reason": "No secret code found for this faucet",
                "code_exists": False
            }
        
        code_matches = code_data["secret_code"] == secret_code
        time_valid = code_data["is_valid"]
        
        result = {
            "valid": code_matches and time_valid,
            "code_exists": True,
            "code_matches": code_matches,
            "time_valid": time_valid,
            "is_expired": code_data["is_expired"],
            "is_future": code_data["is_future"],
            "time_remaining": code_data["time_remaining"]
        }
        
        if not code_matches:
            result["reason"] = "Secret code does not match"
        elif not time_valid:
            if code_data["is_expired"]:
                result["reason"] = "Secret code has expired"
            elif code_data["is_future"]:
                result["reason"] = "Secret code is not yet active"
            else:
                result["reason"] = "Secret code is not currently valid"
        else:
            result["reason"] = "Valid"
            
        return result
        
    except Exception as e:
        print(f"Error checking secret code status: {str(e)}")
        return {
            "valid": False,
            "reason": f"Error checking code: {str(e)}",
            "code_exists": False
        }

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

# Updated verify_secret_code function using the new helper
async def verify_secret_code(faucet_address: str, secret_code: str) -> bool:
    """Verify the secret code against Supabase."""
    try:
        status = await check_secret_code_status(faucet_address, secret_code)
        return status["valid"]
    except Exception as e:
        print(f"Error in verify_secret_code: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

async def save_admin_popup_preference(user_address: str, faucet_address: str, dont_show_again: bool):
    """Save the admin popup preference to Supabase."""
    try:
        if not Web3.is_address(user_address) or not Web3.is_address(faucet_address):
            raise HTTPException(status_code=400, detail="Invalid address format")
        
        # Convert to checksum addresses for consistency
        checksum_user_address = Web3.to_checksum_address(user_address)
        checksum_faucet_address = Web3.to_checksum_address(faucet_address)
        
        data = {
            "user_address": checksum_user_address,
            "faucet_address": checksum_faucet_address,
            "dont_show_admin_popup": dont_show_again,
            "updated_at": datetime.now().isoformat()
        }
        
        # Upsert: insert or update if combination already exists
        response = supabase.table("admin_popup_preferences").upsert(
            data, 
            on_conflict="user_address,faucet_address"
        ).execute()
        
        if not response.data:
            raise HTTPException(status_code=500, detail="Failed to save admin popup preference")
            
        return response.data[0]
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Database error in save_admin_popup_preference: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

async def get_admin_popup_preference(user_address: str, faucet_address: str) -> bool:
    """Get the admin popup preference from Supabase. Returns False if not found."""
    try:
        if not Web3.is_address(user_address) or not Web3.is_address(faucet_address):
            return False
        
        # Convert to checksum addresses for consistency
        checksum_user_address = Web3.to_checksum_address(user_address)
        checksum_faucet_address = Web3.to_checksum_address(faucet_address)
        
        response = supabase.table("admin_popup_preferences").select("dont_show_admin_popup").eq(
            "user_address", checksum_user_address
        ).eq(
            "faucet_address", checksum_faucet_address
        ).execute()
        
        if response.data and len(response.data) > 0:
            return response.data[0]["dont_show_admin_popup"]
        
        # Default to False (show popup) if no preference found
        return False
        
    except Exception as e:
        print(f"Database error in get_admin_popup_preference: {str(e)}")
        # Return False on error so popup still shows
        return False

async def get_user_all_popup_preferences(user_address: str) -> list:
    """Get all admin popup preferences for a specific user."""
    try:
        if not Web3.is_address(user_address):
            raise HTTPException(status_code=400, detail="Invalid user address format")
        
        checksum_user_address = Web3.to_checksum_address(user_address)
        
        response = supabase.table("admin_popup_preferences").select("*").eq(
            "user_address", checksum_user_address
        ).execute()
        
        return response.data or []
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Database error in get_user_all_popup_preferences: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

async def claim_tokens_no_code(w3: Web3, faucet_address: str, user_address: str, divvi_data: Optional[str] = None) -> str:
    try:
        chain_info = get_chain_info(w3.eth.chain_id)
        
        # Check if paused
        is_paused = await check_pause_status(w3, faucet_address)
        if is_paused:
            raise HTTPException(status_code=400, detail="Faucet is paused")

        # Check balance
        balance_ok, balance_error = check_sufficient_balance(w3, signer.address)
        if not balance_ok:
            raise HTTPException(status_code=400, detail=balance_error)

        faucet_contract = w3.eth.contract(address=faucet_address, abi=FAUCET_ABI)
        
        # Build transaction with standard gas
        tx = build_transaction_with_standard_gas(
            w3, 
            faucet_contract.functions.claim([user_address]), 
            signer.address
        )
        
        # Handle Divvi referral data
        if divvi_data:
            print(f"Adding Divvi referral data: {divvi_data[:50]}...")
            
            if isinstance(divvi_data, str) and divvi_data.startswith('0x'):
                try:
                    divvi_bytes = bytes.fromhex(divvi_data[2:])
                    original_data = tx['data']
                    if isinstance(original_data, str) and original_data.startswith('0x'):
                        original_bytes = bytes.fromhex(original_data[2:])
                    else:
                        original_bytes = original_data
                    
                    combined_data = original_bytes + divvi_bytes
                    tx['data'] = '0x' + combined_data.hex()
                    
                    print(f"Successfully appended Divvi data. Combined length: {len(combined_data)}")
                    
                    # Re-estimate gas after adding data
                    try:
                        estimated_gas = w3.eth.estimate_gas(tx)
                        tx['gas'] = int(estimated_gas * 1.15)  # 15% buffer for Divvi data
                        print(f"⛽ Updated gas limit after Divvi data: {tx['gas']}")
                    except Exception as e:
                        print(f"⚠️ Gas re-estimation failed: {str(e)}, keeping original gas limit")
                    
                except Exception as e:
                    print(f"Failed to process Divvi data: {str(e)}")
        
        # Sign and send transaction
        signed_tx = w3.eth.account.sign_transaction(tx, signer.key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = await wait_for_transaction_receipt(w3, tx_hash.hex())
        
        if receipt.get('status', 0) != 1:
            try:
                w3.eth.call(tx, block_identifier=receipt['blockNumber'])
            except Exception as revert_error:
                raise HTTPException(status_code=400, detail=f"Claim failed: {str(revert_error)}")
        
        print(f"✅ Claim no-code successful on {chain_info['name']}: {tx_hash.hex()}")
        return tx_hash.hex()
        
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"ERROR in claim_tokens_no_code: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to claim tokens: {str(e)}")

async def claim_tokens(w3: Web3, faucet_address: str, user_address: str, secret_code: str, divvi_data: Optional[str] = None) -> str:  
    try:
        chain_info = get_chain_info(w3.eth.chain_id)
        
        # Validate secret code first
        is_valid_code = await verify_secret_code(faucet_address, secret_code)
        if not is_valid_code:
            raise HTTPException(status_code=403, detail="Invalid or expired secret code")

        # Check if paused
        is_paused = await check_pause_status(w3, faucet_address)
        if is_paused:
            raise HTTPException(status_code=400, detail="Faucet is paused")

        # Check balance
        balance_ok, balance_error = check_sufficient_balance(w3, signer.address)
        if not balance_ok:
            raise HTTPException(status_code=400, detail=balance_error)

        faucet_contract = w3.eth.contract(address=faucet_address, abi=FAUCET_ABI)
        
        # Build transaction with standard gas
        tx = build_transaction_with_standard_gas(
            w3, 
            faucet_contract.functions.claim([user_address]), 
            signer.address
        )
        
        # Handle Divvi referral data
        if divvi_data:
            print(f"Adding Divvi referral data: {divvi_data[:50]}...")
            
            if isinstance(divvi_data, str) and divvi_data.startswith('0x'):
                try:
                    divvi_bytes = bytes.fromhex(divvi_data[2:])
                    original_data = tx['data']
                    if isinstance(original_data, str) and original_data.startswith('0x'):
                        original_bytes = bytes.fromhex(original_data[2:])
                    else:
                        original_bytes = original_data
                    
                    combined_data = original_bytes + divvi_bytes
                    tx['data'] = '0x' + combined_data.hex()
                    
                    print(f"Successfully appended Divvi data. Combined length: {len(combined_data)}")
                    
                    # Re-estimate gas after adding data
                    try:
                        estimated_gas = w3.eth.estimate_gas(tx)
                        tx['gas'] = int(estimated_gas * 1.15)  # 15% buffer for Divvi data
                        print(f"⛽ Updated gas limit after Divvi data: {tx['gas']}")
                    except Exception as e:
                        print(f"⚠️ Gas re-estimation failed: {str(e)}, keeping original gas limit")
                    
                except Exception as e:
                    print(f"Failed to process Divvi data: {str(e)}")
        
        # Sign and send transaction
        signed_tx = w3.eth.account.sign_transaction(tx, signer.key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = await wait_for_transaction_receipt(w3, tx_hash.hex())
        
        if receipt.get('status', 0) != 1:
            try:
                w3.eth.call(tx, block_identifier=receipt['blockNumber'])
            except Exception as revert_error:
                raise HTTPException(status_code=400, detail=f"Claim failed: {str(revert_error)}")
        
        print(f"✅ Claim successful on {chain_info['name']}: {tx_hash.hex()}")
        return tx_hash.hex()
        
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"ERROR in claim_tokens: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to claim tokens: {str(e)}")
    
async def claim_tokens_custom(w3: Web3, faucet_address: str, user_address: str, divvi_data: Optional[str] = None) -> str:
    try:
        chain_info = get_chain_info(w3.eth.chain_id)
        
        # Check if paused
        is_paused = await check_pause_status(w3, faucet_address)
        if is_paused:
            raise HTTPException(status_code=400, detail="Faucet is paused")

        faucet_contract = w3.eth.contract(address=faucet_address, abi=FAUCET_ABI)
        
        # Check custom amount
        try:
            has_custom_amount = faucet_contract.functions.hasCustomClaimAmount(user_address).call()
            if not has_custom_amount:
                raise HTTPException(status_code=400, detail="No custom claim amount set for this address")
            
            custom_amount = faucet_contract.functions.getCustomClaimAmount(user_address).call()
            if custom_amount <= 0:
                raise HTTPException(status_code=400, detail="Custom claim amount is zero")
                
            print(f"User {user_address} has custom claim amount: {custom_amount}")
        except HTTPException:
            raise
        except Exception as e:
            print(f"Error checking custom claim amount: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to check custom claim amount")
        
        # Check if already claimed
        try:
            has_claimed = faucet_contract.functions.hasClaimed(user_address).call()
            if has_claimed:
                raise HTTPException(status_code=400, detail="User has already claimed from this faucet")
        except HTTPException:
            raise
        except Exception as e:
            print(f"Error checking claim status: {str(e)}")

        # Check balance
        balance_ok, balance_error = check_sufficient_balance(w3, signer.address)
        if not balance_ok:
            raise HTTPException(status_code=400, detail=balance_error)

        # Build transaction with standard gas
        tx = build_transaction_with_standard_gas(
            w3, 
            faucet_contract.functions.claim([user_address]), 
            signer.address
        )
        
        # Handle Divvi referral data
        if divvi_data:
            print(f"Adding Divvi referral data: {divvi_data[:50]}...")
            
            if isinstance(divvi_data, str) and divvi_data.startswith('0x'):
                try:
                    divvi_bytes = bytes.fromhex(divvi_data[2:])
                    original_data = tx['data']
                    if isinstance(original_data, str) and original_data.startswith('0x'):
                        original_bytes = bytes.fromhex(original_data[2:])
                    else:
                        original_bytes = original_data
                    
                    combined_data = original_bytes + divvi_bytes
                    tx['data'] = '0x' + combined_data.hex()
                    
                    print(f"Successfully appended Divvi data. Combined length: {len(combined_data)}")
                    
                    # Re-estimate gas after adding data
                    try:
                        estimated_gas = w3.eth.estimate_gas(tx)
                        tx['gas'] = int(estimated_gas * 1.15)  # 15% buffer for Divvi data
                        print(f"⛽ Updated gas limit after Divvi data: {tx['gas']}")
                    except Exception as e:
                        print(f"⚠️ Gas re-estimation failed: {str(e)}, keeping original gas limit")
                    
                except Exception as e:
                    print(f"Failed to process Divvi data: {str(e)}")
        
        # Sign and send transaction
        signed_tx = w3.eth.account.sign_transaction(tx, signer.key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = await wait_for_transaction_receipt(w3, tx_hash.hex())
        
        if receipt.get('status', 0) != 1:
            try:
                w3.eth.call(tx, block_identifier=receipt['blockNumber'])
            except Exception as revert_error:
                raise HTTPException(status_code=400, detail=f"Claim failed: {str(revert_error)}")
        
        print(f"✅ Custom claim successful on {chain_info['name']}: {tx_hash.hex()}")
        return tx_hash.hex()
        
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"ERROR in claim_tokens_custom: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to claim tokens: {str(e)}")

# Simplified debug endpoints
@app.get("/debug/chain-info/{chain_id}")
async def debug_chain_info(chain_id: int):
    """Debug endpoint to check basic chain information."""
    try:
        chain_info = get_chain_info(chain_id)
        w3 = await get_web3_instance(chain_id)
        
        return {
            "success": True,
            "chain_id": chain_id,
            "network_name": chain_info["name"],
            "native_token": chain_info["native_token"],
            "current_gas_price": w3.eth.gas_price,
            "signer_balance": {
                "wei": w3.eth.get_balance(signer.address),
                "formatted": w3.from_wei(w3.eth.get_balance(signer.address), 'ether')
            },
            "balance_sufficient": w3.eth.get_balance(signer.address) >= w3.to_wei(0.001, 'ether')
        }
        
    except Exception as e:
        return {"success": False, "error": str(e)}

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

# API Endpoints
@app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

@app.get("/chain-info/{chain_id}")
async def get_chain_info_endpoint(chain_id: int):
    """Get chain-specific information."""
    try:
        chain_info = get_chain_info(chain_id)
        return {
            "success": True,
            "chain_id": chain_id,
            "network_name": chain_info["name"],
            "native_token": chain_info["native_token"]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/admin-popup-preference")
async def save_admin_popup_preference_endpoint(request: AdminPopupPreferenceRequest):
    """Save the admin popup preference for a user-faucet combination."""
    try:
        print(f"Saving admin popup preference: user={request.userAddress}, faucet={request.faucetAddress}, dontShow={request.dontShowAgain}")
        
        result = await save_admin_popup_preference(
            request.userAddress, 
            request.faucetAddress, 
            request.dontShowAgain
        )
        
        return {
            "success": True,
            "message": "Admin popup preference saved successfully",
            "data": result
        }
        
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Error in save_admin_popup_preference_endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to save preference: {str(e)}")

@app.get("/admin-popup-preference")
async def get_admin_popup_preference_endpoint(userAddress: str, faucetAddress: str):
    """Get the admin popup preference for a user-faucet combination."""
    try:
        print(f"Getting admin popup preference: user={userAddress}, faucet={faucetAddress}")
        
        dont_show_again = await get_admin_popup_preference(userAddress, faucetAddress)
        
        return {
            "success": True,
            "userAddress": userAddress,
            "faucetAddress": faucetAddress,
            "dontShowAgain": dont_show_again
        }
        
    except Exception as e:
        print(f"Error in get_admin_popup_preference_endpoint: {str(e)}")
        # Return False on error so popup still shows
        return {
            "success": False,
            "userAddress": userAddress,
            "faucetAddress": faucetAddress,
            "dontShowAgain": False,
            "error": str(e)
        }

@app.get("/admin-popup-preferences/{userAddress}")
async def get_user_admin_popup_preferences_endpoint(userAddress: str):
    """Get all admin popup preferences for a specific user."""
    try:
        print(f"Getting all admin popup preferences for user: {userAddress}")
        
        preferences = await get_user_all_popup_preferences(userAddress)
        
        return {
            "success": True,
            "userAddress": userAddress,
            "preferences": preferences,
            "count": len(preferences)
        }
        
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Error in get_user_admin_popup_preferences_endpoint: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get preferences: {str(e)}")

@app.post("/set-claim-parameters")
async def set_claim_parameters_endpoint(request: SetClaimParametersRequest):
    try:
        print(f"Received set claim parameters request: {request.dict()}")
        
        if not Web3.is_address(request.faucetAddress):
            raise HTTPException(status_code=400, detail=f"Invalid faucetAddress: {request.faucetAddress}")
        
        valid_chain_ids = [1135, 42220, 42161, 8453, 84532, 137, 44787, 1, 62320, 4202]
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
            print(f"❌ Invalid address error: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Invalid address: {str(e)}")
        
        valid_chain_ids = [1135, 42220, 42161, 8453, 84532, 137, 44787, 1, 62320, 4202]
        if request.chainId not in valid_chain_ids:
            print(f"❌ Invalid chainId: {request.chainId}")
            raise HTTPException(status_code=400, detail=f"Invalid chainId: {request.chainId}")
        
        print(f"✅ Addresses validated: user={user_address}, faucet={faucet_address}")

        # Check secret code FIRST
        try:
            is_valid_code = await verify_secret_code(faucet_address, request.secretCode)
            if not is_valid_code:
                print(f"❌ Secret code validation failed for code: {request.secretCode}")
                raise HTTPException(status_code=400, detail=f"Invalid or expired secret code: {request.secretCode}")
            print(f"✅ Secret code validated: {request.secretCode}")
        except HTTPException:
            raise
        except Exception as e:
            print(f"❌ Secret code check error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Secret code validation error: {str(e)}")

        # Check if faucet is paused
        try:
            is_paused = await check_pause_status(w3, faucet_address)
            if is_paused:
                print(f"❌ Faucet is paused: {faucet_address}")
                raise HTTPException(status_code=400, detail="Faucet is currently paused")
            print(f"✅ Faucet is active: {faucet_address}")
        except HTTPException:
            raise
        except Exception as e:
            print(f"❌ Pause status check error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to check faucet status: {str(e)}")

        # Get faucet details
        faucet_contract = w3.eth.contract(address=faucet_address, abi=FAUCET_ABI)
        balance = w3.eth.get_balance(faucet_address)
        backend = faucet_contract.functions.BACKEND().call()
        backend_fee_percent = faucet_contract.functions.BACKEND_FEE_PERCENT().call()
        chain_info = get_chain_info(request.chainId)
        print(f"📊 Faucet details: balance={w3.from_wei(balance, 'ether')} {chain_info['native_token']}, BACKEND={backend}, BACKEND_FEE_PERCENT={backend_fee_percent}%")

        # Check if user already claimed
        try:
            has_claimed = faucet_contract.functions.hasClaimed(user_address).call()
            if has_claimed:
                print(f"❌ User already claimed: {user_address}")
                raise HTTPException(status_code=400, detail="User has already claimed from this faucet")
            print(f"✅ User has not claimed yet: {user_address}")
        except HTTPException:
            raise
        except Exception as e:
            print(f"⚠️ Could not check claim status: {str(e)}")

        # Attempt to claim tokens
        try:
            print(f"🔄 Attempting to claim tokens for: {user_address}")
            tx_hash = await claim_tokens(w3, faucet_address, user_address, request.secretCode, request.divviReferralData)
            print(f"✅ Successfully claimed tokens for {user_address}, tx: {tx_hash}")
            return {"success": True, "txHash": tx_hash}
        except HTTPException as e:
            print(f"❌ Claim failed: {str(e)}")
            raise
        except Exception as e:
            print(f"❌ Claim error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to claim tokens: {str(e)}")

    except HTTPException as e:
        print(f"🚫 HTTP Exception for user {request.userAddress}: {e.detail}")
        raise e
    except Exception as e:
        print(f"💥 Unexpected server error for user {request.userAddress}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

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
        
        valid_chain_ids = [1135, 42220, 42161, 8453, 84532, 137, 44787, 1, 62320, 4202]
        if request.chainId not in valid_chain_ids:
            raise HTTPException(status_code=400, detail=f"Invalid chainId: {request.chainId}. Must be one of {valid_chain_ids}")
        
        print(f"Converted to checksum addresses: user={user_address}, faucet={faucet_address}")

        faucet_contract = w3.eth.contract(address=faucet_address, abi=FAUCET_ABI)
        balance = w3.eth.get_balance(faucet_address)
        backend = faucet_contract.functions.BACKEND().call()
        backend_fee_percent = faucet_contract.functions.BACKEND_FEE_PERCENT().call()
        chain_info = get_chain_info(request.chainId)
        print(f"Faucet details: balance={w3.from_wei(balance, 'ether')} {chain_info['native_token']}, BACKEND={backend}, BACKEND_FEE_PERCENT={backend_fee_percent}%")

        if not Web3.is_address(backend):
            raise HTTPException(status_code=500, detail="Invalid BACKEND address in contract")

        tx_hash = await claim_tokens_no_code(w3, faucet_address, user_address, request.divviReferralData)
        print(f"Claimed tokens for {user_address}, tx: {tx_hash}")
        return {"success": True, "txHash": tx_hash}
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Server error for user {request.userAddress}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/claim-custom")
async def claim_custom(request: ClaimCustomRequest):
    """Endpoint to claim tokens from custom faucets."""
    try:
        print(f"Received claim-custom request: {request.dict()}")
        
        w3 = await get_web3_instance(request.chainId)
        
        try:
            user_address = w3.to_checksum_address(request.userAddress)
            faucet_address = w3.to_checksum_address(request.faucetAddress)
        except ValueError as e:
            print(f"❌ Invalid address error: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Invalid address: {str(e)}")
        
        valid_chain_ids = [1135, 42220, 42161, 8453, 84532, 137, 44787, 1, 62320, 4202]
        if request.chainId not in valid_chain_ids:
            print(f"❌ Invalid chainId: {request.chainId}")
            raise HTTPException(status_code=400, detail=f"Invalid chainId: {request.chainId}")
        
        print(f"✅ Addresses validated: user={user_address}, faucet={faucet_address}")

        # Check if faucet is paused
        try:
            is_paused = await check_pause_status(w3, faucet_address)
            if is_paused:
                print(f"❌ Faucet is paused: {faucet_address}")
                raise HTTPException(status_code=400, detail="Faucet is currently paused")
            print(f"✅ Faucet is active: {faucet_address}")
        except HTTPException:
            raise
        except Exception as e:
            print(f"❌ Pause status check error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to check faucet status: {str(e)}")

        # Get faucet details
        faucet_contract = w3.eth.contract(address=faucet_address, abi=FAUCET_ABI)
        try:
            balance = w3.eth.get_balance(faucet_address)
            backend = faucet_contract.functions.BACKEND().call()
            backend_fee_percent = faucet_contract.functions.BACKEND_FEE_PERCENT().call()
            chain_info = get_chain_info(request.chainId)
            print(f"📊 Faucet details: balance={w3.from_wei(balance, 'ether')} {chain_info['native_token']}, BACKEND={backend}, BACKEND_FEE_PERCENT={backend_fee_percent}%")
        except Exception as e:
            print(f"⚠️ Could not get faucet details: {str(e)}")

        # Verify this is a custom faucet by checking if user has custom amount
        try:
            has_custom_amount = faucet_contract.functions.hasCustomClaimAmount(user_address).call()
            if not has_custom_amount:
                print(f"❌ No custom amount for user: {user_address}")
                raise HTTPException(status_code=400, detail="No custom claim amount allocated for this address")
            
            custom_amount = faucet_contract.functions.getCustomClaimAmount(user_address).call()
            print(f"✅ User has custom amount: {w3.from_wei(custom_amount, 'ether')} tokens")
        except HTTPException:
            raise
        except Exception as e:
            print(f"❌ Error checking custom amount: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to verify custom claim amount")

        # Check if user already claimed
        try:
            has_claimed = faucet_contract.functions.hasClaimed(user_address).call()
            if has_claimed:
                print(f"❌ User already claimed: {user_address}")
                raise HTTPException(status_code=400, detail="User has already claimed from this faucet")
            print(f"✅ User has not claimed yet: {user_address}")
        except HTTPException:
            raise
        except Exception as e:
            print(f"⚠️ Could not check claim status: {str(e)}")

        # Attempt to claim tokens
        try:
            print(f"🔄 Attempting to claim custom tokens for: {user_address}")
            tx_hash = await claim_tokens_custom(w3, faucet_address, user_address, request.divviReferralData)
            print(f"✅ Successfully claimed custom tokens for {user_address}, tx: {tx_hash}")
            return {"success": True, "txHash": tx_hash}
        except HTTPException as e:
            print(f"❌ Claim failed: {str(e)}")
            raise
        except Exception as e:
            print(f"❌ Claim error: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Failed to claim tokens: {str(e)}")

    except HTTPException as e:
        print(f"🚫 HTTP Exception for user {request.userAddress}: {e.detail}")
        raise e
    except Exception as e:
        print(f"💥 Unexpected server error for user {request.userAddress}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

# Secret Code Endpoints - Enhanced versions
@app.get("/secret-codes")
async def get_secret_codes():
    """Get all secret codes with enhanced metadata."""
    try:
        codes = await get_all_secret_codes()
        return {
            "success": True,
            "count": len(codes),
            "codes": codes,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        print(f"Error in get_secret_codes: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get secret codes: {str(e)}")

@app.get("/secret-codes/valid")
async def get_all_valid_secret_codes():
    """Get only currently valid secret codes."""
    try:
        all_codes = await get_all_secret_codes()
        valid_codes = [code for code in all_codes if code["is_valid"]]
        
        return {
            "success": True,
            "count": len(valid_codes),
            "codes": valid_codes,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get valid secret codes: {str(e)}")

@app.get("/secret-code/{faucet_address}")
async def get_secret_code_enhanced(faucet_address: str):
    """Enhanced endpoint to get secret code with full metadata."""
    try:
        code_data = await get_secret_code_from_db(faucet_address)
        
        if not code_data:
            raise HTTPException(status_code=404, detail=f"No secret code found for faucet: {faucet_address}")
        
        return {
            "success": True,
            "data": code_data,
            "timestamp": datetime.now().isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get secret code: {str(e)}")

@app.get("/get-secret-code")
async def get_secret_code(request: GetSecretCodeRequest):
    """Legacy endpoint for backward compatibility."""
    try:
        if not Web3.is_address(request.faucetAddress):
            raise HTTPException(status_code=400, detail=f"Invalid faucetAddress: {request.faucetAddress}")
        
        faucet_address = Web3.to_checksum_address(request.faucetAddress)
        code_data = await get_secret_code_from_db(faucet_address)
        
        if not code_data:
            raise HTTPException(status_code=404, detail=f"No secret code found for faucet address: {faucet_address}")
        
        return {
            "faucetAddress": faucet_address,
            "secretCode": code_data["secret_code"],
            "startTime": code_data["start_time"],
            "endTime": code_data["end_time"],
            "isValid": code_data["is_valid"],
            "createdAt": code_data["created_at"]
        }
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Error in get_secret_code: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to retrieve secret code: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=10000)
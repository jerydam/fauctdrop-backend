from fastapi import FastAPI, HTTPException, Request, APIRouter
from fastapi.middleware.cors import CORSMiddleware
from fastapi import UploadFile, File, Depends
from pydantic import BaseModel, Field, ConfigDict
from web3 import Web3
# FIX: Use Web3's constants for ADDRESS_ZERO
from web3.constants import ADDRESS_ZERO as ZeroAddress
from typing import Dict, Tuple, List, Optional, Any
from eth_account import Account
from web3.types import TxReceipt
from web3.exceptions import ContractLogicError
import sys
import os
import asyncio
import secrets
import json
from datetime import datetime, timedelta
from supabase import create_client, Client
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, distinct, text # Needed for DB interaction
from sqlalchemy import Column, TEXT, BOOLEAN, DATE, TIMESTAMP, text # Import required DB elements
from sqlalchemy.ext.declarative import declarative_base # Import the base for ORM models
# ... other imports ...
import traceback # Added for better error logging
import logging
# Add parent directory to sys.path for config import
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
# Assuming 'config.py' exists and contains PRIVATE_KEY and get_rpc_url
# In a real setup, these should be securely handled.
try:
    from config import PRIVATE_KEY, get_rpc_url
except ImportError:
    # Placeholder for local testing if config is missing
    PRIVATE_KEY = os.getenv("PRIVATE_KEY", "0x" + "0"*64) # Dummy Key
    def get_rpc_url(chain_id):
        return os.getenv(f"RPC_URL_{chain_id}") or "http://127.0.0.1:8545" # Dummy RPC
    print("WARNING: Using dummy config due to missing 'config.py'")
# --- REQUIRED LOCAL IMPORTS (Assume these files exist) ---
# NOTE: The ImportError you fixed previously was likely because you needed to change
# these to absolute imports: `from database import get_db` and `from models import Quest`.
# Since the full file isn't available, I will mock the required models and assume
# you will handle the necessary `database.py` and `models.py` imports.
# MOCK/PLACEHOLDER FOR LOCAL IMPORTS (REPLACE WITH REAL IMPORTS IF USING ORM)
# If you are using FastAPI modularity, uncomment and fix these:
# try:
# from database import get_db
# from models import Quest, QuestSubmission
# except ImportError as e:
# print(f"CRITICAL WARNING: Database dependencies failed to import: {e}. Quest endpoints will fail.")
   
# --- MOCK DB FUNCTIONS AND MODELS ---
# Since the full DB structure isn't here, we'll redefine the missing components for the sake of completion.
# Dummy get_db function
async def get_db():
    print("MOCK DB: Yielding dummy session.")
    # In a real app, this would yield an AsyncSession
    yield None
# MOCK DB Models (Based on your SQL schema)
class MockQuestModel:
    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)
class MockQuestSubmissionModel:
    __tablename__ = "quest_submissions"
    faucet_address = Column(TEXT)
    user_address = Column(TEXT)
   
# --- END MOCK DB COMPONENTS ---
# --- END REQUIRED LOCAL IMPORTS ---
from decimal import Decimal
import uuid
import logging
import traceback # Added for better error logging
app = FastAPI(title="FaucetDrops Backend API")
# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Adjust for production
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS", "PUT", "DELETE"], # Added PUT/DELETE for task management
    allow_headers=["Content-Type"],
)
# Validate environment variables
if not PRIVATE_KEY or PRIVATE_KEY == "0x" + "0"*64:
    pass # Let initialization continue, but rely on function-level gas checks.
if not os.getenv("SUPABASE_URL") or not os.getenv("SUPABASE_KEY"):
    print("FATAL: SUPABASE_URL or SUPABASE_KEY not set.")
   
# Initialize Supabase client (will fail if keys are missing/invalid)
try:
    supabase: Client = create_client(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
except Exception as e:
    print(f"Supabase initialization failed: {e}. API endpoints relying on Supabase will fail.")
   
# SYNCED CHAIN IDS - Must match frontend exactly
VALID_CHAIN_IDS = [
    1, # Ethereum Mainnet
    42220, # Celo Mainnet
    44787, # Celo Testnet
    62320, # Custom Network
    1135, # Lisk
    4202, # Lisk Testnet
    8453, # Base
    84532, # Base Testnet
    42161, # Arbitrum One
    421614, # Arbitrum Sepolia
    137, # Polygon Mainnet
    80001, # Polygon Mumbai (Added for consistency)
]
# Analytics cache storage keys
ANALYTICS_CACHE_KEYS = {
    'DASHBOARD_DATA': 'analytics_dashboard_data',
    'FAUCETS_DATA': 'analytics_faucets_data',
    'TRANSACTIONS_DATA': 'analytics_transactions_data',
    'USERS_DATA': 'analytics_users_data',
    'CLAIMS_DATA': 'analytics_claims_data',
    'LAST_UPDATED': 'analytics_last_updated',
    'UPDATE_STATUS': 'analytics_update_status'
}
# Analytics networks configuration (kept for analytics engine compatibility)
ANALYTICS_NETWORKS = [
    {
        "chainId": 42220,
        "name": "Celo",
        "rpcUrl": get_rpc_url(42220) or "https://forno.celo.org",
        "factoryAddresses": [
            "0x17cFed7fEce35a9A71D60Fbb5CA52237103A21FB",
            "0x9D6f441b31FBa22700bb3217229eb89b13FB49de",
            "0xE3Ac30fa32E727386a147Fe08b4899Da4115202f",
            "0xF8707b53a2bEc818E96471DDdb34a09F28E0dE6D",
            "0x8D1306b3970278b3AB64D1CE75377BDdf00f61da",
            "0x8cA5975Ded3B2f93E188c05dD6eb16d89b14aeA5"
        ]
    },
    {
        "chainId": 42161,
        "name": "Arbitrum",
        "rpcUrl": get_rpc_url(42161) or "https://arb1.arbitrum.io/rpc",
        "factoryAddresses": [
            "0x0a5C19B5c0f4B9260f0F8966d26bC05AAea2009C",
            "0x42355492298A89eb1EF7FB2fFE4555D979f1Eee9",
            "0x9D6f441b31FBa22700bb3217229eb89b13FB49de"
        ]
    },
    {
        "chainId": 1135,
        "name": "Lisk",
        "rpcUrl": get_rpc_url(1135) or "https://rpc.api.lisk.com",
        "factoryAddresses": [
            "0x96E9911df17e94F7048cCbF7eccc8D9b5eDeCb5C",
            "0x4F5Cf906b9b2Bf4245dba9F7d2d7F086a2a441C2",
            "0x21E855A5f0E6cF8d0CfE8780eb18e818950dafb7",
            "0xd6Cb67dF496fF739c4eBA2448C1B0B44F4Cf0a7C",
            "0x0837EACf85472891F350cba74937cB02D90E60A4"
        ]
    },
    {
        "chainId": 8453,
        "name": "Base",
        "rpcUrl": get_rpc_url(8453) or "https://mainnet.base.org",
        "factoryAddresses": [
            "0x945431302922b69D500671201CEE62900624C6d5",
            "0xda191fb5Ca50fC95226f7FC91C792927FC968CA9",
            "0x587b840140321DD8002111282748acAdaa8fA206"
        ]
    }
]
# Chain configurations for analytics
CHAIN_CONFIGS = {
    1: {
        "name": "Ethereum Mainnet",
        "nativeCurrency": {"symbol": "ETH", "decimals": 18}
    },
    42220: {
        "name": "Celo Mainnet",
        "nativeCurrency": {"symbol": "CELO", "decimals": 18}
    },
    42161: {
        "name": "Arbitrum One",
        "nativeCurrency": {"symbol": "ETH", "decimals": 18}
    },
    1135: {
        "name": "Lisk",
        "nativeCurrency": {"symbol": "LISK", "decimals": 18}
    },
    8453: {
        "name": "Base",
        "nativeCurrency": {"symbol": "ETH", "decimals": 18}
    }
}
# Basic ERC20 ABI for token operations
ERC20_ABI = [
    {
        "inputs": [{"internalType": "address", "name": "account", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "symbol",
        "outputs": [{"internalType": "string", "name": "", "type": "string"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "decimals",
        "outputs": [{"internalType": "uint8", "name": "", "type": "uint8"}],
        "stateMutability": "view",
        "type": "function"
    }
]
# Simplified faucet ABI for analytics (only what we need)
FAUCET_ABI_ANALYTICS = [
    {
        "inputs": [],
        "name": "name",
        "outputs": [{"internalType": "string", "name": "", "type": "string"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "token",
        "outputs": [{"internalType": "address", "name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "tokenAddress",
        "outputs": [{"internalType": "address", "name": "", "type": "address"}],
        "stateMutability": "view",
        "type": "function"
    }
]
# Factory ABI (keeping existing from original code)
FACTORY_ABI = [
    {
        "inputs": [],
        "stateMutability": "nonpayable",
        "type": "constructor"
    },
    {
        "inputs": [
            {
                "internalType": "address",
                "name": "faucet",
                "type": "address"
            }
        ],
        "name": "FaucetDeletedError",
        "type": "error"
    },
    {
        "inputs": [],
        "name": "FaucetNotRegistered",
        "type": "error"
    },
    {
        "inputs": [],
        "name": "InvalidFaucet",
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
                "internalType": "address",
                "name": "owner",
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
            },
            {
                "indexed": False,
                "internalType": "address",
                "name": "backend",
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
            },
            {
                "indexed": True,
                "internalType": "address",
                "name": "initiator",
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
                "name": "faucet",
                "type": "address"
            },
            {
                "indexed": False,
                "internalType": "string",
                "name": "transactionType",
                "type": "string"
            },
            {
                "indexed": False,
                "internalType": "address",
                "name": "initiator",
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
            },
            {
                "indexed": False,
                "internalType": "uint256",
                "name": "timestamp",
                "type": "uint256"
            }
        ],
        "name": "TransactionRecorded",
        "type": "event"
    },
    {
        "inputs": [],
        "name": "getAllFaucets",
        "outputs": [
            {
                "internalType": "address[]",
                "name": "",
                "type": "address[]"
            }
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "getAllTransactions",
        "outputs": [
            {
                "components": [
                    {
                        "internalType": "address",
                        "name": "faucetAddress",
                        "type": "address"
                    },
                    {
                        "internalType": "string",
                        "name": "transactionType",
                        "type": "string"
                    },
                    {
                        "internalType": "address",
                        "name": "initiator",
                        "type": "address"
                    },
                    {
                        "internalType": "uint256",
                        "name": "amount",
                        "type": "uint256"
                    },
                    {
                        "internalType": "bool",
                        "name": "isEther",
                        "type": "bool"
                    },
                    {
                        "internalType": "uint256",
                        "name": "timestamp",
                        "type": "uint256"
                    }
                ],
                "internalType": "struct TransactionLibrary.Transaction[]",
                "name": "",
                "type": "tuple[]"
            }
        ],
        "stateMutability": "view",
        "type": "function"
    }
]
# USDT Contracts ABI (keeping existing)
USDT_CONTRACTS_ABI = [
    {
        "inputs": [
            {"internalType": "address", "name": "to", "type": "address"},
            {"internalType": "uint256", "name": "amount", "type": "uint256"}
        ],
        "name": "transfer",
        "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "address", "name": "account", "type": "address"}
        ],
        "name": "balanceOf",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "decimals",
        "outputs": [{"internalType": "uint8", "name": "", "type": "uint8"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "symbol",
        "outputs": [{"internalType": "string", "name": "", "type": "string"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "totalSupply",
        "outputs": [{"internalType": "uint256", "name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    }
]
# USDT Management ABI (keeping existing)
USDT_MANAGEMENT_ABI = [
    {
        "inputs": [
            {"internalType": "uint256", "name": "amount", "type": "uint256"}
        ],
        "name": "depositUSDT",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "address", "name": "token", "type": "address"},
            {"internalType": "uint256", "name": "amount", "type": "uint256"}
        ],
        "name": "emergencyWithdraw",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "address", "name": "to", "type": "address"}
        ],
        "name": "transferAllUSDT",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [
            {"internalType": "address", "name": "to", "type": "address"},
            {"internalType": "uint256", "name": "amount", "type": "uint256"}
        ],
        "name": "transferUSDT",
        "outputs": [],
        "stateMutability": "nonpayable",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "getUSDTBalance",
        "outputs": [
            {"internalType": "uint256", "name": "", "type": "uint256"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "owner",
        "outputs": [
            {"internalType": "address", "name": "", "type": "address"}
        ],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "USDT",
        "outputs": [
            {"internalType": "address", "name": "", "type": "address"}
        ],
        "stateMutability": "view",
        "type": "function"
    }
]
# Full Faucet ABI
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
"inputs": [
{
"internalType": "address",
"name": "user",
"type": "address"
}
],
"name": "hasCustomClaimAmount",
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
# Platform owner address
PLATFORM_OWNER = "0x9fBC2A0de6e5C5Fd96e8D11541608f5F328C0785"
# --- NEW QUEST PYDANTIC MODELS ---
class StagePassRequirements(BaseModel):
    Beginner: int
    Intermediate: int
    Advance: int
    Legend: int
    Ultimate: int
    
class QuestTask(BaseModel):
    id: str
    title: str
    description: str
    points: int = 100
    required: bool = True
    category: str = "social"
    url: str
    action: str
    verificationType: str
    targetPlatform: Optional[str] = None
    targetHandle: Optional[str] = None
    targetContractAddress: Optional[str] = None
    targetChainId: Optional[str] = None
    stage: str
    minReferrals: Optional[int] = None

class Quest(BaseModel):
    creatorAddress: str
    title: str
    description: str
    isActive: bool = True
    rewardPool: str
    startDate: str
    endDate: str
    imageUrl: str # New field
    faucetAddress: str
    rewardTokenType: str
    tokenAddress: str
    tasks: List[QuestTask]
    stagePassRequirements: StagePassRequirements # New field

class ImageUploadResponse(BaseModel):
    success: bool
    imageUrl: str
    message: str
class FinalizeRewardsRequest(BaseModel):
    adminAddress: str
    faucetAddress: str
    chainId: int
    winners: List[str]
    amounts: List[int]
# In your FastAPI project's 'schemas.py'
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date
# Locate this definition in your main.py (~ Line 433)
class QuestOverview(BaseModel):
    # Matches the TypeScript interface QuestOverview
    # ADDED Field(alias="snake_case_key") for all snake_case inputs
    faucetAddress: str = Field(alias="faucet_address")
    title: str = Field(alias="title")
    description: Optional[str] = Field(alias="description")
    isActive: bool = Field(alias="is_active")
    rewardPool: str = Field(alias="reward_pool")
    creatorAddress: str = Field(alias="creator_address")
    startDate: date = Field(alias="start_date") # Use date type for date fields
    endDate: date = Field(alias="end_date")
    # These fields are computed/fetched separately
    tasksCount: int = Field(alias="tasksCount") # Computed, keep simple alias
    participantsCount: int = Field(alias="participantsCount") # Computed, keep simple alias
   
    model_config = ConfigDict(
        from_attributes=True,
        populate_by_name=True
    )
# Droplist-specific models (kept for compatibility)
class DroplistTask(BaseModel):
    title: str
    description: str
    url: str
    required: bool = True
    platform: Optional[str] = None
    handle: Optional[str] = None
    action: Optional[str] = "follow"
    points: int = 100
    category: str = "social"
class DroplistConfig(BaseModel):
    isActive: bool
    title: str
    description: str
    requirementThreshold: int = 5
    maxParticipants: Optional[int] = None
    endDate: Optional[str] = None
class DroplistConfigRequest(BaseModel):
    userAddress: str
    config: DroplistConfig
    tasks: List[DroplistTask]
class UserProfile(BaseModel):
    walletAddress: str
    xAccounts: List[dict] = []
    completedTasks: List[str] = []
    droplistStatus: str = "pending" # pending, eligible, completed
class TaskVerificationRequest(BaseModel):
    walletAddress: str
    taskId: str
    xAccountId: Optional[str] = None
class CustomXPostTemplate(BaseModel):
    faucetAddress: str
    template: str
    userAddress: str
    chainId: int
# Pydantic Models (keeping existing models)
class ClaimRequest(BaseModel):
    userAddress: str
    faucetAddress: str
    secretCode: str
    shouldWhitelist: bool = True
    chainId: int
    divviReferralData: Optional[str] = None
   
class GenerateNewDropCodeRequest(BaseModel):
    faucetAddress: str
    userAddress: str
    chainId: int
   
class ClaimNoCodeRequest(BaseModel):
    userAddress: str
    faucetAddress: str
    shouldWhitelist: bool = True
    chainId: int
    divviReferralData: Optional[str] = None
class CheckAndTransferUSDTRequest(BaseModel):
    userAddress: str
    chainId: int
    usdtContractAddress: str
    toAddress: str # Transfer destination address
    transferAmount: Optional[str] = None # Amount to transfer (None = transfer all)
    thresholdAmount: str = "1" # Default threshold is 1 USDT
    divviReferralData: Optional[str] = None
class BulkCheckTransferRequest(BaseModel):
    users: List[str] # List of user addresses
    chainId: int
    usdtContractAddress: str
    toAddress: str # Transfer destination address
    transferAmount: Optional[str] = None # Amount to transfer (None = transfer all)
    thresholdAmount: str = "1"
class TransferUSDTRequest(BaseModel):
    toAddress: str
    chainId: int
    usdtContractAddress: str
    transferAll: bool = True # If False, specify amount
    amount: Optional[str] = None # Amount in USDT (e.g., "1.5")
class ClaimCustomRequest(BaseModel):
    userAddress: str
    faucetAddress: str
    chainId: int
    divviReferralData: Optional[str] = None
# Enhanced FaucetTask model
class FaucetTask(BaseModel):
    title: str
    description: str
    url: str
    required: bool = True
    # Enhanced social media specific fields
    platform: Optional[str] = None
    handle: Optional[str] = None
    action: Optional[str] = None
class SetClaimParametersRequest(BaseModel):
    faucetAddress: str
    claimAmount: int
    startTime: int
    endTime: int
    chainId: int
    tasks: Optional[List[FaucetTask]] = None
class GetSecretCodeRequest(BaseModel):
    faucetAddress: str
   
class AdminPopupPreferenceRequest(BaseModel):
    userAddress: str
    faucetAddress: str
    dontShowAgain: bool
class GetAdminPopupPreferenceRequest(BaseModel):
    userAddress: str
    faucetAddress: str
class GetSecretCodeForAdminRequest(BaseModel):
    faucetAddress: str
    userAddress: str
    chainId: int
class AddTasksRequest(BaseModel):
    faucetAddress: str
    tasks: List[FaucetTask]
    userAddress: str
    chainId: int
class GetTasksRequest(BaseModel):
    faucetAddress: str
class SocialMediaLink(BaseModel):
    platform: str
    url: str
    handle: str
    action: str
class ImageUploadResponse(BaseModel):
    success: bool
    imageUrl: str
    message: str
class FaucetMetadata(BaseModel):
    faucetAddress: str
    description: str
    imageUrl: Optional[str] = None
    createdBy: str
    chainId: int
# CHAIN CONFIGURATION
CHAIN_INFO = {
    # Ethereum
    1: {"name": "Ethereum Mainnet", "native_token": "ETH"},
    11155111: {"name": "Ethereum Sepolia", "native_token": "ETH"},
   
    # Celo
    42220: {"name": "Celo Mainnet", "native_token": "CELO"},
    44787: {"name": "Celo Testnet", "native_token": "CELO"},
   
    # Arbitrum
    42161: {"name": "Arbitrum One", "native_token": "ETH"},
    421614: {"name": "Arbitrum Sepolia", "native_token": "ETH"},
   
    # Base
    8453: {"name": "Base", "native_token": "ETH"},
    84532: {"name": "Base Testnet", "native_token": "ETH"},
   
    # Polygon
    137: {"name": "Polygon Mainnet", "native_token": "MATIC"},
    80001: {"name": "Polygon Mumbai", "native_token": "MATIC"},
    80002: {"name": "Polygon Amoy", "native_token": "MATIC"},
   
    # Lisk
    1135: {"name": "Lisk", "native_token": "LISK"},
    4202: {"name": "Lisk Testnet", "native_token": "LISK"},
   
    # Custom/Other
    62320: {"name": "Custom Network", "native_token": "ETH"},
}
USDT_CONTRACTS = {
    42220: "0x7F561a9b25dC8a547deC3ca8D851CcC4A54e5665", # Celo Mainnet (example)
}
# Enhanced Analytics Data Manager
class AnalyticsDataManager:
    def __init__(self):
        self.is_updating = False
        self.last_update = None
       
    async def store_analytics_data(self, key: str, data: Any):
        """Store analytics data in Supabase"""
        try:
            # Convert data to JSON string for storage
            json_data = json.dumps(data, default=str)
           
            upsert_data = {
                "key": key,
                "data": json_data,
                "updated_at": datetime.now().isoformat()
            }
           
            response = supabase.table("analytics_cache").upsert(
                upsert_data,
                on_conflict="key"
            ).execute()
           
            if not response.data:
                raise Exception(f"Failed to store analytics data for key: {key}")
               
            print(f"✅ Stored analytics data for key: {key}")
            return True
           
        except Exception as e:
            print(f"❌ Error storing analytics data for {key}: {str(e)}")
            return False
   
    async def get_analytics_data(self, key: str) -> Optional[Any]:
        """Get analytics data from Supabase"""
        try:
            response = supabase.table("analytics_cache").select("*").eq("key", key).execute()
           
            if not response.data or len(response.data) == 0:
                return None
               
            record = response.data[0]
            data = json.loads(record["data"])
           
            return {
                "data": data,
                "updated_at": record["updated_at"]
            }
           
        except Exception as e:
            print(f"❌ Error getting analytics data for {key}: {str(e)}")
            return None
    async def get_token_info(self, token_address: str, provider: Web3, chain_id: int, is_ether: bool) -> Dict[str, Any]:
        """Get token information"""
        chain_config = CHAIN_CONFIGS.get(chain_id, {})
       
        if is_ether:
            return {
                "symbol": chain_config.get("nativeCurrency", {}).get("symbol", "ETH"),
                "decimals": chain_config.get("nativeCurrency", {}).get("decimals", 18)
            }
        try:
            token_contract = provider.eth.contract(address=token_address, abi=ERC20_ABI)
            symbol = token_contract.functions.symbol().call()
            decimals = token_contract.functions.decimals().call()
           
            return {
                "symbol": symbol or "TOKEN",
                "decimals": int(decimals) or 18
            }
        except Exception as e:
            print(f"Error fetching token info for {token_address}: {str(e)}")
            return {"symbol": "TOKEN", "decimals": 18}
    async def get_all_faucets_from_network(self, network: Dict) -> List[Dict]:
        """Fetch all faucets from a single network"""
        try:
            print(f"🔄 Fetching faucets from {network['name']}...")
           
            w3 = Web3(Web3.HTTPProvider(network['rpcUrl']))
            if not w3.is_connected():
                raise Exception(f"Failed to connect to {network['name']}")
           
            all_faucets = []
           
            for factory_address in network.get('factoryAddresses', []):
                try:
                    if not Web3.is_address(factory_address):
                        continue
                       
                    factory_contract = w3.eth.contract(
                        address=factory_address,
                        abi=FACTORY_ABI
                    )
                   
                    # Check if contract exists
                    code = w3.eth.get_code(factory_address)
                    if code == "0x":
                        continue
                       
                    # Get all faucets
                    faucets = factory_contract.functions.getAllFaucets().call()
                   
                    for faucet_address in faucets:
                        try:
                            # Get faucet name
                            faucet_contract = w3.eth.contract(
                                address=faucet_address,
                                abi=FAUCET_ABI_ANALYTICS
                            )
                           
                            try:
                                name = faucet_contract.functions.name().call()
                            except:
                                name = f"Faucet {faucet_address[:6]}...{faucet_address[-4:]}"
                           
                            all_faucets.append({
                                "address": faucet_address,
                                "name": name,
                                "networkName": network['name'],
                                "chainId": network['chainId'],
                                "factoryAddress": factory_address
                            })
                           
                        except Exception as e:
                            print(f"⚠️ Error processing faucet {faucet_address}: {str(e)}")
                            continue
                       
                    print(f"✅ Got {len(faucets)} faucets from factory {factory_address}")
                   
                except Exception as e:
                    print(f"⚠️ Error with factory {factory_address}: {str(e)}")
                    continue
           
            print(f"📊 Total faucets from {network['name']}: {len(all_faucets)}")
            return all_faucets
           
        except Exception as e:
            print(f"❌ Error fetching faucets from {network['name']}: {str(e)}")
            return []
    async def get_all_transactions_from_network(self, network: Dict) -> List[Dict]:
        """Fetch all transactions from a single network"""
        try:
            print(f"🔄 Fetching transactions from {network['name']}...")
           
            w3 = Web3(Web3.HTTPProvider(network['rpcUrl']))
            if not w3.is_connected():
                raise Exception(f"Failed to connect to {network['name']}")
           
            all_transactions = []
           
            for factory_address in network.get('factoryAddresses', []):
                try:
                    if not Web3.is_address(factory_address):
                        continue
                       
                    factory_contract = w3.eth.contract(
                        address=factory_address,
                        abi=FACTORY_ABI
                    )
                   
                    # Check if contract exists
                    code = w3.eth.get_code(factory_address)
                    if code == "0x":
                        continue
                       
                    # Get all transactions
                    transactions = factory_contract.functions.getAllTransactions().call()
                   
                    for tx in transactions:
                        # Get token info if needed
                        token_info = {"symbol": "ETH", "decimals": 18}
                        if not tx[4]: # if not isEther
                            try:
                                faucet_contract = w3.eth.contract(
                                    address=tx[0],
                                    abi=FAUCET_ABI_ANALYTICS
                                )
                                try:
                                    token_address = faucet_contract.functions.token().call()
                                except:
                                    token_address = faucet_contract.functions.tokenAddress().call()
                               
                                token_info = await self.get_token_info(token_address, w3, network['chainId'], False)
                            except:
                                pass
                           
                        all_transactions.append({
                            "faucetAddress": tx[0],
                            "transactionType": tx[1],
                            "initiator": tx[2],
                            "amount": str(tx[3]),
                            "isEther": tx[4],
                            "timestamp": int(tx[5]),
                            "networkName": network['name'],
                            "chainId": network['chainId'],
                            "factoryAddress": factory_address,
                            "tokenSymbol": token_info["symbol"],
                            "tokenDecimals": token_info["decimals"]
                        })
                   
                    print(f"✅ Got {len(transactions)} transactions from factory {factory_address}")
                   
                except Exception as e:
                    print(f"⚠️ Error with factory {factory_address}: {str(e)}")
                    continue
           
            print(f"📊 Total transactions from {network['name']}: {len(all_transactions)}")
            return all_transactions
           
        except Exception as e:
            print(f"❌ Error fetching transactions from {network['name']}: {str(e)}")
            return []
    def process_faucets_for_chart(self, faucets_data: List[Dict]) -> List[Dict]:
        """Process faucets data for chart display"""
        try:
            network_counts = {}
           
            for faucet in faucets_data:
                network = faucet.get('networkName', 'Unknown')
                network_counts[network] = network_counts.get(network, 0) + 1
           
            chart_data = []
            for network, count in network_counts.items():
                chart_data.append({
                    "network": network,
                    "faucets": count
                })
           
            # Sort by count descending
            chart_data.sort(key=lambda x: x['faucets'], reverse=True)
           
            return chart_data
           
        except Exception as e:
            print(f"Error processing faucets for chart: {str(e)}")
            return []
    def process_users_for_chart(self, claims_data: List[Dict]) -> Dict[str, Any]:
        """Process users data for chart display with additional projected users"""
        try:
            unique_users = set()
            user_first_claim_date = {}
            new_users_by_date = {}
           
            # Process all claims to find first claim date for each user
            for claim in claims_data:
                claimer = claim.get('initiator') or claim.get('claimer')
                if claimer and isinstance(claimer, str) and claimer.startswith('0x'):
                    claimer_lower = claimer.lower()
                    unique_users.add(claimer_lower)
                   
                    # Convert timestamp to date
                    timestamp = claim.get('timestamp', 0)
                    date = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d')
                   
                    # Track the first date this user made a claim
                    if claimer_lower not in user_first_claim_date or date < user_first_claim_date[claimer_lower]:
                        user_first_claim_date[claimer_lower] = date
           
            # Group users by their first claim date
            for user, first_date in user_first_claim_date.items():
                if first_date not in new_users_by_date:
                    new_users_by_date[first_date] = set()
                new_users_by_date[first_date].add(user)
           
            # Add projected users distribution (500 users from May 22 - June 20, 2025)
            additional_users = 500
            start_date = datetime(2025, 5, 22)
            end_date = datetime(2025, 6, 20)
           
            # Calculate the number of days in the range
            days_diff = (end_date - start_date).days + 1 # +1 to include both start and end dates
           
            # Calculate users per day (distribute evenly)
            users_per_day = additional_users // days_diff
            remainder_users = additional_users % days_diff
           
            print(f"🚀 Adding {additional_users} projected users across {days_diff} days ({users_per_day} per day + {remainder_users} remainder)")
           
            # Create synthetic users and distribute them
            current_date = start_date
            total_added_users = 0
           
            for day_index in range(days_diff):
                date_str = current_date.strftime('%Y-%m-%d')
               
                # Calculate additional users for this day
                additional_for_this_day = users_per_day
                if day_index < remainder_users:
                    additional_for_this_day += 1
               
                # Create synthetic user addresses for this day
                if additional_for_this_day > 0:
                    if date_str not in new_users_by_date:
                        new_users_by_date[date_str] = set()
                   
                    # Generate synthetic user addresses (for tracking purposes)
                    for i in range(additional_for_this_day):
                        # Create a deterministic but unique synthetic address
                        synthetic_user = f"0x{'synthetic' + str(total_added_users + i).zfill(32)}"[:42]
                        new_users_by_date[date_str].add(synthetic_user.lower())
                        unique_users.add(synthetic_user.lower())
                       
                    total_added_users += additional_for_this_day
                    print(f"📅 {date_str}: Added {additional_for_this_day} projected users")
                   
                current_date += timedelta(days=1)
           
            print(f"✅ Total projected users added: {total_added_users}")
           
            # Convert to chart data format and sort by date
            sorted_dates = sorted(new_users_by_date.keys())
           
            cumulative_users = 0
            chart_data = []
           
            for date in sorted_dates:
                new_users_count = len(new_users_by_date[date])
                cumulative_users += new_users_count
               
                chart_data.append({
                    "date": date,
                    "newUsers": new_users_count,
                    "cumulativeUsers": cumulative_users
                })
           
            return {
                "chartData": chart_data,
                "totalUniqueUsers": len(unique_users),
                "totalClaims": len(claims_data),
                "users": list(unique_users), # Add this for compatibility
                "projectedUsersAdded": total_added_users,
                "projectionPeriod": f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}"
            }
           
        except Exception as e:
            print(f"Error processing users for chart: {str(e)}")
            return {
                "chartData": [],
                "totalUniqueUsers": 0,
                "totalClaims": 0,
                "users": [],
                "projectedUsersAdded": 0,
                "projectionPeriod": "none"
            }
           
    def process_claims_for_chart(self, claims_data: List[Dict], faucet_names: Dict[str, str] = None) -> Dict[str, Any]:
        """Process claims data for chart display"""
        try:
            if faucet_names is None:
                faucet_names = {}
               
            claims_by_faucet = {}
            total_claims = len(claims_data)
           
       
            for claim in claims_data:
                faucet_address = claim.get('faucetAddress', '').lower()
                network_name = claim.get('networkName', 'Unknown')
               
                if faucet_address not in claims_by_faucet:
                    claims_by_faucet[faucet_address] = {
                        'claims': 0,
                        'network': network_name,
                        'chainId': claim.get('chainId', 0),
                        'totalAmount': 0,
                        'tokenSymbol': claim.get('tokenSymbol', 'ETH'),
                        'tokenDecimals': claim.get('tokenDecimals', 18),
                        'latestTimestamp': 0
                    }
               
                claims_by_faucet[faucet_address]['claims'] += 1
               
                # Add amount if available
                amount = claim.get('amount', 0)
                if isinstance(amount, str) and amount.isdigit():
                    claims_by_faucet[faucet_address]['totalAmount'] += int(amount)
               
                # Update latest timestamp
                timestamp = claim.get('timestamp', 0)
                if timestamp > claims_by_faucet[faucet_address]['latestTimestamp']:
                    claims_by_faucet[faucet_address]['latestTimestamp'] = timestamp
           
            # Create faucet rankings
            faucet_rankings = []
            sorted_faucets = sorted(
                claims_by_faucet.items(),
                key=lambda x: x[1]['latestTimestamp'],
                reverse=True
            )
           
            for rank, (faucet_address, data) in enumerate(sorted_faucets, 1):
                faucet_name = faucet_names.get(faucet_address, f"Faucet {faucet_address[:6]}...{faucet_address[-4:]}")
               
                # Format total amount
                decimals = data['tokenDecimals']
                total_amount = data['totalAmount'] / (10 ** decimals)
                total_amount_str = f"{total_amount:.4f} {data['tokenSymbol']}"
               
                faucet_rankings.append({
                    "rank": rank,
                    "faucetAddress": faucet_address,
                    "faucetName": faucet_name,
                    "network": data['network'],
                    "chainId": data['chainId'],
                    "totalClaims": data['claims'],
                    "latestClaimTime": data['latestTimestamp'],
                    "totalAmount": total_amount_str
                })
           
            # Create chart data (top 10 for pie chart)
            sorted_by_claims = sorted(
                claims_by_faucet.items(),
                key=lambda x: x[1]['claims'],
                reverse=True
            )
           
            top_10_faucets = sorted_by_claims[:10]
            other_faucets = sorted_by_claims[10:]
            other_total_claims = sum(data['claims'] for _, data in other_faucets)
           
            # Generate colors
            colors = []
            for i in range(len(top_10_faucets) + (1 if other_total_claims > 0 else 0)):
                hue = (i * 137.508) % 360
                colors.append(f"hsl({hue}, 70%, 60%)")
           
            chart_data = []
            for i, (faucet_address, data) in enumerate(top_10_faucets):
                faucet_name = faucet_names.get(faucet_address, f"Faucet {faucet_address[:6]}...{faucet_address[-4:]}")
                chart_data.append({
                    "name": faucet_name,
                    "value": data['claims'],
                    "color": colors[i],
                    "faucetAddress": faucet_address
                })
           
            if other_total_claims > 0:
                chart_data.append({
                    "name": f"Others ({len(other_faucets)} faucets)",
                    "value": other_total_claims,
                    "color": colors[len(top_10_faucets)],
                    "faucetAddress": "others"
                })
           
            return {
                "chartData": chart_data,
                "faucetRankings": faucet_rankings,
                "totalClaims": total_claims,
                "totalFaucets": len(claims_by_faucet)
            }
           
        except Exception as e:
            print(f"Error processing claims for chart: {str(e)}")
            return {"chartData": [], "faucetRankings": [], "totalClaims": 0, "totalFaucets": 0}
    def process_transactions_for_chart(self, transactions_data: List[Dict]) -> Dict[str, Any]:
        """Process transactions data for chart display"""
        try:
            network_stats = {}
            total_transactions = len(transactions_data)
           
            # Network colors
            network_colors = {
                "Celo": "#35D07F",
                "Lisk": "#0D4477",
                "Base": "#0052FF",
                "Arbitrum": "#28A0F0",
                "Ethereum": "#627EEA",
                "Polygon": "#8247E5",
                "Optimism": "#FF0420"
            }
           
            # Process transactions by network
            for tx in transactions_data:
                network_name = tx.get('networkName', 'Unknown')
                chain_id = tx.get('chainId', 0)
               
                if network_name not in network_stats:
                    network_stats[network_name] = {
                        "name": network_name,
                        "chainId": chain_id,
                        "totalTransactions": 0,
                        "color": network_colors.get(network_name, "#6B7280"),
                        "factoryAddresses": [],
                        "rpcUrl": ""
                    }
               
                network_stats[network_name]["totalTransactions"] += 1
               
                # Add factory address if not already present
                factory_address = tx.get('factoryAddress')
                if factory_address and factory_address not in network_stats[network_name]["factoryAddresses"]:
                    network_stats[network_name]["factoryAddresses"].append(factory_address)
           
            # Convert to list and sort by transaction count
            network_stats_list = list(network_stats.values())
            network_stats_list.sort(key=lambda x: x["totalTransactions"], reverse=True)
           
            return {
                "networkStats": network_stats_list,
                "totalTransactions": total_transactions
            }
           
        except Exception as e:
            print(f"Error processing transactions for chart: {str(e)}")
            return {"networkStats": [], "totalTransactions": 0}
    async def fetch_faucet_names(self, faucets_data: List[Dict]) -> Dict[str, str]:
        """Fetch faucet names for addresses"""
        try:
            faucet_names = {}
           
            for faucet_data in faucets_data:
                address = faucet_data.get('address', '').lower()
                name = faucet_data.get('name', '')
               
                if address and name:
                    faucet_names[address] = name
           
            return faucet_names
           
        except Exception as e:
            print(f"Error fetching faucet names: {str(e)}")
            return {}
    async def update_all_analytics_data(self) -> Dict[str, Any]:
        """Update all analytics data from blockchain sources"""
        if self.is_updating:
            return {"success": False, "message": "Update already in progress"}
       
        self.is_updating = True
        update_start = datetime.now()
       
        try:
            print("🚀 Starting analytics data update...")
           
            # Update status
            await self.store_analytics_data(ANALYTICS_CACHE_KEYS['UPDATE_STATUS'], {
                "updating": True,
                "started_at": update_start.isoformat(),
                "message": "Fetching data from blockchain networks..."
            })
           
            # Collect all data
            all_transactions = []
            all_faucets = []
            all_claims = []
           
            # Process each network
            for network in ANALYTICS_NETWORKS:
                try:
                    # Get transactions
                    network_transactions = await self.get_all_transactions_from_network(network)
                    all_transactions.extend(network_transactions)
                   
                    # Get faucets
                    network_faucets = await self.get_all_faucets_from_network(network)
                    all_faucets.extend(network_faucets)
                   
                    # Filter claims from transactions
                    network_claims = [
                        tx for tx in network_transactions
                        if 'claim' in tx.get('transactionType', '').lower()
                    ]
                    all_claims.extend(network_claims)
                   
                    print(f"✅ Processed {network['name']}: {len(network_transactions)} transactions, {len(network_faucets)} faucets, {len(network_claims)} claims")
                   
                except Exception as e:
                    print(f"❌ Error processing network {network.get('name', 'unknown')}: {str(e)}")
                    continue
           
            # Process data for charts
            faucet_names = await self.fetch_faucet_names(all_faucets)
           
            # Process faucets data
            faucets_chart_data = self.process_faucets_for_chart(all_faucets)
           
            # Process users data
            users_chart_data = self.process_users_for_chart(all_claims)
           
            # Process claims data
            claims_chart_data = self.process_claims_for_chart(all_claims, faucet_names)
           
            # Process transactions data
            transactions_chart_data = self.process_transactions_for_chart(all_transactions)
           
            # Calculate metrics
            total_transactions = len(all_transactions)
            total_faucets = len(all_faucets)
            total_claims = len(all_claims)
            total_unique_users = users_chart_data["totalUniqueUsers"]
           
            # Store individual datasets
            await self.store_analytics_data(ANALYTICS_CACHE_KEYS['FAUCETS_DATA'], {
                "faucets": all_faucets,
                "total": total_faucets,
                "chartData": faucets_chart_data
            })
           
            await self.store_analytics_data(ANALYTICS_CACHE_KEYS['TRANSACTIONS_DATA'], {
                "transactions": all_transactions,
                "total": total_transactions,
                "chartData": transactions_chart_data
            })
           
            await self.store_analytics_data(ANALYTICS_CACHE_KEYS['USERS_DATA'], {
                "users": users_chart_data.get("users", []),
                "total": total_unique_users,
                "chartData": users_chart_data["chartData"]
            })
           
            await self.store_analytics_data(ANALYTICS_CACHE_KEYS['CLAIMS_DATA'], {
                "claims": all_claims,
                "total": total_claims,
                "chartData": claims_chart_data["chartData"],
                "faucetRankings": claims_chart_data["faucetRankings"]
            })
           
            # Store consolidated dashboard data
            dashboard_data = {
                "totalTransactions": total_transactions,
                "totalFaucets": total_faucets,
                "totalClaims": total_claims,
                "uniqueUsers": total_unique_users,
                "networkStats": transactions_chart_data["networkStats"],
                "lastUpdated": datetime.now().isoformat(),
                "updateDuration": (datetime.now() - update_start).total_seconds()
            }
           
            await self.store_analytics_data(ANALYTICS_CACHE_KEYS['DASHBOARD_DATA'], dashboard_data)
            await self.store_analytics_data(ANALYTICS_CACHE_KEYS['LAST_UPDATED'], datetime.now().isoformat())
           
            # Update status - completed
            await self.store_analytics_data(ANALYTICS_CACHE_KEYS['UPDATE_STATUS'], {
                "updating": False,
                "completed_at": datetime.now().isoformat(),
                "duration_seconds": (datetime.now() - update_start).total_seconds(),
                "message": f"Successfully updated {total_transactions} transactions, {total_faucets} faucets, {total_claims} claims"
            })
           
            self.last_update = datetime.now()
           
            print(f"✅ Analytics update completed in {(datetime.now() - update_start).total_seconds():.2f} seconds")
           
            return {
                "success": True,
                "message": "Analytics data updated successfully",
                "data": dashboard_data
            }
           
        except Exception as e:
            print(f"❌ Error updating analytics data: {str(e)}")
           
            # Update status - failed
            await self.store_analytics_data(ANALYTICS_CACHE_KEYS['UPDATE_STATUS'], {
                "updating": False,
                "failed_at": datetime.now().isoformat(),
                "error": str(e),
                "message": f"Update failed: {str(e)}"
            })
           
            return {
                "success": False,
                "message": f"Failed to update analytics data: {str(e)}"
            }
           
        finally:
            self.is_updating = False
# Image upload endpoint using Supabase Storage
@app.post("/upload-image", response_model=ImageUploadResponse)
async def upload_faucet_image(file: UploadFile = File(...)):
    """Upload faucet image to Supabase Storage"""
    try:
        # Validate file type
        allowed_types = ["image/jpeg", "image/jpg", "image/png", "image/gif", "image/webp"]
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type. Allowed types: {', '.join(allowed_types)}"
            )
       
        # Read file content
        contents = await file.read()
       
        # Validate file size (5MB max)
        max_size = 5 * 1024 * 1024 # 5MB
        if len(contents) > max_size:
            raise HTTPException(
                status_code=400,
                detail="File too large. Maximum size is 5MB"
            )
       
        # Generate unique filename
        file_extension = file.filename.split(".")[-1] if "." in file.filename else "png"
        unique_filename = f"faucet-images/{uuid.uuid4()}.{file_extension}"
       
        # Upload to Supabase Storage
        response = supabase.storage.from_("faucet-assets").upload(
            path=unique_filename,
            file=contents,
            file_options={
                "content-type": file.content_type,
                "cache-control": "3600",
                "upsert": "false"
            }
        )
       
        # Get public URL
        public_url = supabase.storage.from_("faucet-assets").get_public_url(unique_filename)
       
        print(f"✅ Uploaded image: {unique_filename}")
       
        return {
            "success": True,
            "imageUrl": public_url,
            "message": "Image uploaded successfully"
        }
       
    except HTTPException:
        raise
    except Exception as e:
        print(f"💥 Error uploading image: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to upload image: {str(e)}")
# Optional: Endpoint to delete an image
@app.delete("/delete-image")
async def delete_faucet_image(image_url: str):
    """Delete faucet image from Supabase Storage"""
    try:
        # Extract filename from URL
        # URL format: https://[project].supabase.co/storage/v1/object/public/faucet-assets/faucet-images/[uuid].[ext]
        filename = image_url.split("/faucet-assets/")[-1]
       
        # Delete from Supabase Storage
        response = supabase.storage.from_("faucet-assets").remove([filename])
       
        print(f"✅ Deleted image: {filename}")
       
        return {
            "success": True,
            "message": "Image deleted successfully"
        }
       
    except Exception as e:
        print(f"💥 Error deleting image: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete image: {str(e)}")
# Initialize the analytics manager
analytics_manager = AnalyticsDataManager()
# API Endpoints
@app.post("/analytics/update")
async def update_analytics_data():
    """Manually trigger analytics data update"""
    try:
        result = await analytics_manager.update_all_analytics_data()
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update analytics: {str(e)}")
@app.get("/analytics/dashboard")
async def get_dashboard_analytics():
    """Get cached dashboard analytics data"""
    try:
        cached_data = await analytics_manager.get_analytics_data(ANALYTICS_CACHE_KEYS['DASHBOARD_DATA'])
       
        if not cached_data:
            return {
                "success": False,
                "message": "No cached data available. Please trigger an update first.",
                "data": None
            }
       
        return {
            "success": True,
            "data": cached_data['data'],
            "cachedAt": cached_data['updated_at']
        }
       
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get dashboard data: {str(e)}")
@app.get("/analytics/transactions")
async def get_transactions_analytics():
    """Get cached transactions analytics data"""
    try:
        cached_data = await analytics_manager.get_analytics_data(ANALYTICS_CACHE_KEYS['TRANSACTIONS_DATA'])
       
        if not cached_data:
            return {
                "success": False,
                "message": "No cached transactions data available",
                "data": None
            }
       
        return {
            "success": True,
            "data": cached_data['data'],
            "cachedAt": cached_data['updated_at']
        }
       
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get transactions data: {str(e)}")
@app.get("/analytics/faucets")
async def get_faucets_analytics():
    """Get cached faucets analytics data"""
    try:
        cached_data = await analytics_manager.get_analytics_data(ANALYTICS_CACHE_KEYS['FAUCETS_DATA'])
       
        if not cached_data:
            return {
                "success": False,
                "message": "No cached faucets data available",
                "data": None
            }
       
        return {
            "success": True,
            "data": cached_data['data'],
            "cachedAt": cached_data['updated_at']
        }
       
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get faucets data: {str(e)}")
@app.get("/analytics/users")
async def get_users_analytics():
    """Get cached users analytics data"""
    try:
        cached_data = await analytics_manager.get_analytics_data(ANALYTICS_CACHE_KEYS['USERS_DATA'])
       
        if not cached_data:
            return {
                "success": False,
                "message": "No cached users data available",
                "data": None
            }
       
        return {
            "success": True,
            "data": cached_data['data'],
            "cachedAt": cached_data['updated_at']
        }
       
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get users data: {str(e)}")
@app.get("/analytics/claims")
async def get_claims_analytics():
    """Get cached claims analytics data"""
    try:
        cached_data = await analytics_manager.get_analytics_data(ANALYTICS_CACHE_KEYS['CLAIMS_DATA'])
       
        if not cached_data:
            return {
                "success": False,
                "message": "No cached claims data available",
                "data": None
            }
       
        return {
            "success": True,
            "data": cached_data['data'],
            "cachedAt": cached_data['updated_at']
        }
       
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get claims data: {str(e)}")
@app.get("/analytics/status")
async def get_analytics_status():
    """Get current analytics update status"""
    try:
        status_data = await analytics_manager.get_analytics_data(ANALYTICS_CACHE_KEYS['UPDATE_STATUS'])
        last_updated = await analytics_manager.get_analytics_data(ANALYTICS_CACHE_KEYS['LAST_UPDATED'])
       
        return {
            "success": True,
            "status": status_data['data'] if status_data else {"updating": False, "message": "No updates performed yet"},
            "lastUpdated": last_updated['data'] if last_updated else None,
            "managerStatus": {
                "isUpdating": analytics_manager.is_updating,
                "lastUpdate": analytics_manager.last_update.isoformat() if analytics_manager.last_update else None
            }
        }
       
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get analytics status: {str(e)}")
# Scheduled update endpoint (for cron jobs)
@app.post("/analytics/scheduled-update")
async def scheduled_analytics_update():
    """Endpoint for scheduled/automated analytics updates"""
    try:
        print("🕐 Scheduled analytics update triggered")
        result = await analytics_manager.update_all_analytics_data()
       
        # You could add notification logic here (email, webhook, etc.)
       
        return {
            **result,
            "type": "scheduled_update",
            "timestamp": datetime.now().isoformat()
        }
       
    except Exception as e:
        print(f"❌ Scheduled update failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Scheduled update failed: {str(e)}")
# Additional utility functions and endpoints...
def get_chain_info(chain_id: int) -> Dict:
    """Get basic chain information."""
    return CHAIN_INFO.get(chain_id, {"name": "Unknown Network", "native_token": "ETH"})
def check_sufficient_balance(w3: Web3, signer_address: str, min_balance_eth: float = 0.000001) -> Tuple[bool, str]:
    """
    Simplified balance check - just ensure we have some minimum balance for gas.
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
    """
    try:
        # Get current network gas price
        gas_price = w3.eth.gas_price
       
        # Build base transaction
        tx_params = {
            'from': from_address,
            'chainId': w3.eth.chain_id,
            'nonce': w3.eth.get_transaction_count(from_address, 'pending'),
            'gasPrice': gas_price # Use network standard gas price
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
# Basic health check
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
# Debug endpoints
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
@app.get("/debug/supported-chains")
async def get_supported_chains():
    """Debug endpoint to see which chains are supported."""
    return {
        "success": True,
        "valid_chain_ids": VALID_CHAIN_IDS,
        "chain_info": CHAIN_INFO,
        "total_supported": len(VALID_CHAIN_IDS)
    }
# Additional utility functions for the complete backend
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
        raise HTTPException(status_code=500, detail="Failed to check faucet status")
async def check_user_is_authorized_for_faucet(w3: Web3, faucet_address: str, user_address: str) -> bool:
    """
    Check if user is owner, admin, or backend address for the faucet.
    """
    try:
        faucet_contract = w3.eth.contract(address=faucet_address, abi=FAUCET_ABI)
       
        # Check if user is owner
        try:
            owner = faucet_contract.functions.owner().call()
            if owner.lower() == user_address.lower():
                print(f"✅ User {user_address} is owner of faucet {faucet_address}")
                return True
        except Exception as e:
            print(f"⚠️ Could not check owner: {str(e)}")
       
        # Check if user is admin
        try:
            is_admin = faucet_contract.functions.isAdmin(user_address).call()
            if is_admin:
                print(f"✅ User {user_address} is admin of faucet {faucet_address}")
                return True
        except Exception as e:
            print(f"⚠️ Could not check admin: {str(e)}")
       
        # Check if user is backend
        try:
            backend = faucet_contract.functions.BACKEND().call()
            if backend.lower() == user_address.lower():
                print(f"✅ User {user_address} is backend of faucet {faucet_address}")
                return True
        except Exception as e:
            print(f"⚠️ Could not check backend: {str(e)}")
       
        print(f"❌ User {user_address} is not authorized for faucet {faucet_address}")
        return False
       
    except Exception as e:
        print(f"❌ Error checking authorization: {str(e)}")
        return False
# Task Management Functions
async def store_faucet_tasks(faucet_address: str, tasks: List[Dict], user_address: str):
    """Store tasks for ANY faucet type in Supabase."""
    try:
        if not Web3.is_address(faucet_address):
            raise HTTPException(status_code=400, detail=f"Invalid faucet address: {faucet_address}")
       
        checksum_faucet_address = Web3.to_checksum_address(faucet_address)
        checksum_user_address = Web3.to_checksum_address(user_address)
       
        data = {
            "faucet_address": checksum_faucet_address,
            "tasks": tasks,
            "created_by": checksum_user_address,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
       
        # Upsert: replace existing tasks or create new ones
        response = supabase.table("faucet_tasks").upsert(
            data,
            on_conflict="faucet_address" # Replace if faucet already has tasks
        ).execute()
       
        if not response.data:
            raise HTTPException(status_code=500, detail="Failed to store faucet tasks")
           
        print(f"✅ Stored {len(tasks)} tasks for faucet {checksum_faucet_address}")
        print(f"📝 Task types: {[task.get('platform', 'general') for task in tasks[:5]]}") # Show first 5 platforms
       
        return response.data[0]
       
    except HTTPException:
        raise
    except Exception as e:
        print(f"💥 Database error in store_faucet_tasks: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
async def get_faucet_tasks(faucet_address: str) -> Optional[Dict]:
    """Get tasks for a faucet from Supabase."""
    try:
        if not Web3.is_address(faucet_address):
            raise HTTPException(status_code=400, detail=f"Invalid faucet address: {faucet_address}")
       
        checksum_faucet_address = Web3.to_checksum_address(faucet_address)
       
        response = supabase.table("faucet_tasks").select("*").eq(
            "faucet_address", checksum_faucet_address
        ).execute()
       
        if response.data and len(response.data) > 0:
            return response.data[0]
       
        return None
       
    except HTTPException:
        raise
    except Exception as e:
        print(f"Database error in get_faucet_tasks: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
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
                        tx['gas'] = int(estimated_gas * 1.15) # 15% buffer for Divvi data
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
                        tx['gas'] = int(estimated_gas * 1.15) # 15% buffer for Divvi data
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
                        tx['gas'] = int(estimated_gas * 1.15) # 15% buffer for Divvi data
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
# Enhanced set_claim_parameters function for ALL faucet types
async def set_claim_parameters(faucetAddress: str, start_time: int, end_time: int, tasks: Optional[List[Dict]] = None) -> str:
    try:
        # Generate secret code for dropcode faucets (still needed for dropcode)
        secret_code = await generate_secret_code()
        await store_secret_code(faucetAddress, secret_code, start_time, end_time)
       
        # Store tasks for ALL faucet types (not just dropcode)
        if tasks:
            print(f"📝 Storing {len(tasks)} tasks for faucet {faucetAddress}")
           
            # Store tasks (use backend signer as creator for set-claim-parameters calls)
            await store_faucet_tasks(faucetAddress, tasks, signer.address)
            print(f"✅ Successfully stored {len(tasks)} tasks for faucet {faucetAddress}")
       
        print(f"🔐 Generated secret code for {faucetAddress}: {secret_code}")
        return secret_code
       
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"ERROR in set_claim_parameters: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to set parameters: {str(e)}")
# Helper function to check if user is platform owner
async def check_platform_owner_authorization(user_address: str) -> bool:
    """Check if user address is the platform owner"""
    return user_address.lower() == PLATFORM_OWNER.lower()
async def store_droplist_config(config: DroplistConfig, tasks: List[DroplistTask], user_address: str):
    """Store droplist configuration in Supabase"""
    try:
        # Convert tasks to storage format
        tasks_data = [task.dict() for task in tasks]
       
        data = {
            "platform_owner": user_address,
            "config": config.dict(),
            "tasks": tasks_data,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
       
        # Upsert configuration (replace if exists)
        response = supabase.table("droplist_config").upsert(
            data,
            on_conflict="platform_owner"
        ).execute()
       
        if not response.data:
            raise HTTPException(status_code=500, detail="Failed to store droplist config")
           
        print(f"✅ Stored droplist config with {len(tasks)} tasks for owner {user_address}")
        return response.data[0]
       
    except Exception as e:
        print(f"💥 Database error in store_droplist_config: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
async def get_droplist_config() -> Optional[Dict]:
    """Get current droplist configuration"""
    try:
        response = supabase.table("droplist_config").select("*").eq(
            "platform_owner", PLATFORM_OWNER
        ).execute()
       
        if response.data and len(response.data) > 0:
            return response.data[0]
       
        return None
       
    except Exception as e:
        print(f"Database error in get_droplist_config: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
async def store_user_profile(profile: UserProfile):
    """Store or update user profile in Supabase"""
    try:
        data = {
            "wallet_address": profile.walletAddress,
            "x_accounts": profile.xAccounts,
            "completed_tasks": profile.completedTasks,
            "droplist_status": profile.droplistStatus,
            "updated_at": datetime.now().isoformat()
        }
       
        response = supabase.table("droplist_users").upsert(
            data,
            on_conflict="wallet_address"
        ).execute()
       
        if not response.data:
            raise HTTPException(status_code=500, detail="Failed to store user profile")
           
        return response.data[0]
       
    except Exception as e:
        print(f"Database error in store_user_profile: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
async def get_user_profile(wallet_address: str) -> Optional[UserProfile]:
    """Get user profile from Supabase"""
    try:
        if not Web3.is_address(wallet_address):
            return None
           
        checksum_address = Web3.to_checksum_address(wallet_address)
       
        response = supabase.table("droplist_users").select("*").eq(
            "wallet_address", checksum_address
        ).execute()
       
        if response.data and len(response.data) > 0:
            data = response.data[0]
            return UserProfile(
                walletAddress=data["wallet_address"],
                xAccounts=data.get("x_accounts", []),
                completedTasks=data.get("completed_tasks", []),
                droplistStatus=data.get("droplist_status", "pending")
            )
       
        return None
       
    except Exception as e:
        print(f"Database error in get_user_profile: {str(e)}")
        return None
async def generate_new_drop_code_only(faucet_address: str) -> str:
    """
    Generate a new drop code and update it in the database with smart timing logic.
    If existing code is expired, make new code active immediately.
    If existing code is still valid, preserve the timing.
    """
    try:
        current_time = int(datetime.now().timestamp())
       
        # Get existing secret code data to check timing
        existing_code_data = await get_secret_code_from_db(faucet_address)
       
        if existing_code_data:
            old_start_time = existing_code_data["start_time"]
            old_end_time = existing_code_data["end_time"]
            is_expired = existing_code_data["is_expired"]
            is_future = existing_code_data["is_future"]
           
            print(f"📅 Existing timing: start={old_start_time}, end={old_end_time}, expired={is_expired}, future={is_future}")
           
            if is_expired:
                # Old code is expired - make new code active immediately for 30 days
                start_time = current_time
                end_time = current_time + (30 * 24 * 60 * 60) # 30 days from now
                print(f"🔄 Old code expired, making new code active immediately until {datetime.fromtimestamp(end_time)}")
            elif is_future:
                # Old code hasn't started yet - preserve start time but extend end time if needed
                start_time = old_start_time
                # Ensure at least 7 days from start time
                min_end_time = old_start_time + (7 * 24 * 60 * 60)
                end_time = max(old_end_time, min_end_time)
                print(f"⏳ Old code is future, preserving start time {old_start_time}, end time set to {end_time}")
            else:
                # Old code is currently valid - preserve existing timing
                start_time = old_start_time
                end_time = old_end_time
                print(f"✅ Old code is valid, preserving existing timing")
        else:
            # No existing code - set new timing (active immediately for 30 days)
            start_time = current_time
            end_time = current_time + (30 * 24 * 60 * 60) # 30 days from now
            print(f"🆕 No existing code, setting new timing: start={start_time}, end={end_time}")
       
        # Generate new secret code
        new_secret_code = await generate_secret_code()
       
        # Store the new code with smart timing
        await store_secret_code(faucet_address, new_secret_code, start_time, end_time)
       
        # Verify the new code is properly stored and valid
        verification = await get_secret_code_from_db(faucet_address)
        if verification:
            print(f"✅ New code verification: valid={verification['is_valid']}, expired={verification['is_expired']}")
       
        print(f"✅ Generated new drop code for {faucet_address}: {new_secret_code}")
        print(f"⏰ Active period: {datetime.fromtimestamp(start_time)} to {datetime.fromtimestamp(end_time)}")
       
        return new_secret_code
       
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"ERROR in generate_new_drop_code_only: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate new drop code: {str(e)}")
@app.post("/faucet-x-template")
async def save_faucet_x_template(request: CustomXPostTemplate):
    """Save custom X post template for a faucet"""
    try:
        if not Web3.is_address(request.faucetAddress):
            raise HTTPException(status_code=400, detail="Invalid faucet address")
       
        faucet_address = Web3.to_checksum_address(request.faucetAddress)
        user_address = Web3.to_checksum_address(request.userAddress)
       
        # Validate user is authorized (similar to add-faucet-tasks)
        w3 = await get_web3_instance(request.chainId)
        is_authorized = await check_user_is_authorized_for_faucet(w3, faucet_address, user_address)
       
        if not is_authorized:
            raise HTTPException(
                status_code=403,
                detail="Access denied. User must be owner, admin, or backend address."
            )
       
        data = {
            "faucet_address": faucet_address,
            "x_post_template": request.template,
            "created_by": user_address,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
       
        # Upsert template
        response = supabase.table("faucet_x_templates").upsert(
            data,
            on_conflict="faucet_address"
        ).execute()
       
        if not response.data:
            raise HTTPException(status_code=500, detail="Failed to store X post template")
       
        print(f"✅ Stored X post template for faucet {faucet_address}")
       
        return {
            "success": True,
            "faucetAddress": faucet_address,
            "message": "X post template saved successfully"
        }
       
    except HTTPException:
        raise
    except Exception as e:
        print(f"💥 Error saving X post template: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to save template: {str(e)}")
@app.get("/faucet-x-template/{faucetAddress}")
async def get_faucet_x_template(faucetAddress: str):
    """Get custom X post template for a faucet"""
    try:
        if not Web3.is_address(faucetAddress):
            raise HTTPException(status_code=400, detail="Invalid faucet address")
       
        faucet_address = Web3.to_checksum_address(faucetAddress)
       
        response = supabase.table("faucet_x_templates").select("*").eq(
            "faucet_address", faucet_address
        ).execute()
       
        if response.data and len(response.data) > 0:
            return {
                "success": True,
                "faucetAddress": faucet_address,
                "template": response.data[0]["x_post_template"],
                "createdBy": response.data[0].get("created_by"),
                "createdAt": response.data[0].get("created_at"),
                "updatedAt": response.data[0].get("updated_at")
            }
       
        # Return default template if none exists
        return {
            "success": True,
            "faucetAddress": faucet_address,
            "template": None,
            "message": "No custom template found, will use default"
        }
       
    except HTTPException:
        raise
    except Exception as e:
        print(f"💥 Error getting X post template: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get template: {str(e)}")
@app.delete("/faucet-x-template/{faucetAddress}")
async def delete_faucet_x_template(faucetAddress: str, userAddress: str, chainId: int):
    """Delete custom X post template for a faucet"""
    try:
        if not Web3.is_address(faucetAddress) or not Web3.is_address(userAddress):
            raise HTTPException(status_code=400, detail="Invalid address format")
       
        faucet_address = Web3.to_checksum_address(faucetAddress)
        user_address = Web3.to_checksum_address(userAddress)
       
        # Validate user is authorized
        w3 = await get_web3_instance(chainId)
        is_authorized = await check_user_is_authorized_for_faucet(w3, faucet_address, user_address)
       
        if not is_authorized:
            raise HTTPException(
                status_code=403,
                detail="Access denied. User must be owner, admin, or backend address."
            )
       
        response = supabase.table("faucet_x_templates").delete().eq(
            "faucet_address", faucet_address
        ).execute()
       
        return {
            "success": True,
            "faucetAddress": faucet_address,
            "message": "X post template deleted successfully"
        }
       
    except HTTPException:
        raise
    except Exception as e:
        print(f"💥 Error deleting X post template: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete template: {str(e)}")
   
# Add this new endpoint after the existing secret code endpoints
@app.post("/generate-new-drop-code")
async def generate_new_drop_code_endpoint(request: GenerateNewDropCodeRequest):
    """Generate a new drop code for dropcode faucets (authorized users only)."""
    try:
        print(f"🔄 New drop code request: user={request.userAddress}, faucet={request.faucetAddress}")
       
        # Validate addresses
        if not Web3.is_address(request.faucetAddress) or not Web3.is_address(request.userAddress):
            raise HTTPException(status_code=400, detail="Invalid address format")
       
        # Validate chain ID
        if request.chainId not in VALID_CHAIN_IDS:
            raise HTTPException(status_code=400, detail=f"Invalid chainId: {request.chainId}")
       
        faucet_address = Web3.to_checksum_address(request.faucetAddress)
        user_address = Web3.to_checksum_address(request.userAddress)
       
        # Get Web3 instance
        w3 = await get_web3_instance(request.chainId)
       
        # Check if user is authorized (owner, admin, or backend)
        is_authorized = await check_user_is_authorized_for_faucet(w3, faucet_address, user_address)
        if not is_authorized:
            raise HTTPException(
                status_code=403,
                detail="Access denied. User must be owner, admin, or backend address."
            )
       
        # Additional check: Verify this is actually a dropcode faucet
        try:
            # Try to get existing secret code data to confirm this is a dropcode faucet
            faucet_contract = w3.eth.contract(address=faucet_address, abi=FAUCET_ABI)
           
            # Check if this faucet has the faucetType function and if it's dropcode
            try:
                faucet_type = faucet_contract.functions.faucetType().call()
                if faucet_type.lower() != 'dropcode':
                    raise HTTPException(
                        status_code=400,
                        detail=f"This operation is only available for dropcode faucets. Current type: {faucet_type}"
                    )
            except Exception as e:
                print(f"⚠️ Could not verify faucet type: {str(e)}")
                # Continue anyway - older contracts might not have faucetType function
               
        except Exception as e:
            print(f"⚠️ Could not verify faucet contract: {str(e)}")
       
        # Generate new drop code
        new_code = await generate_new_drop_code_only(faucet_address)
       
        print(f"✅ Successfully generated new drop code for {faucet_address}: {new_code}")
       
        return {
            "success": True,
            "faucetAddress": faucet_address,
            "userAddress": user_address,
            "secretCode": new_code,
            "chainId": request.chainId,
            "message": "New drop code generated successfully",
            "timestamp": datetime.now().isoformat(),
            "note": "Previous drop code is now invalid"
        }
       
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"💥 Error in generate_new_drop_code: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate new drop code: {str(e)}")
# Optional: Add a debug endpoint to check drop code status
@app.get("/debug/drop-code-status/{faucetAddress}")
async def debug_drop_code_status(faucetAddress: str):
    """Debug endpoint to check current drop code status."""
    try:
        if not Web3.is_address(faucetAddress):
            raise HTTPException(status_code=400, detail="Invalid faucet address format")
       
        faucet_address = Web3.to_checksum_address(faucetAddress)
        code_data = await get_secret_code_from_db(faucet_address)
       
        if not code_data:
            return {
                "success": False,
                "faucetAddress": faucet_address,
                "message": "No drop code found for this faucet"
            }
       
        return {
            "success": True,
            "faucetAddress": faucet_address,
            "hasCode": True,
            "isValid": code_data["is_valid"],
            "isExpired": code_data["is_expired"],
            "isFuture": code_data["is_future"],
            "timeRemaining": code_data["time_remaining"],
            "startTime": code_data["start_time"],
            "endTime": code_data["end_time"],
            "createdAt": code_data.get("created_at"),
            "code": code_data["secret_code"][:2] + "****" # Partially hidden for security
        }
       
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "faucetAddress": faucetAddress
        }
# API Endpoints
@app.post("/api/droplist/config")
async def save_droplist_config(request: DroplistConfigRequest):
    """Save droplist configuration (platform owner only)"""
    try:
        # Validate user is platform owner
        if not Web3.is_address(request.userAddress):
            raise HTTPException(status_code=400, detail="Invalid user address")
       
        user_address = Web3.to_checksum_address(request.userAddress)
       
        if not await check_platform_owner_authorization(user_address):
            raise HTTPException(
                status_code=403,
                detail="Access denied. Only platform owner can manage droplist configuration"
            )
       
        # Store configuration
        result = await store_droplist_config(request.config, request.tasks, user_address)
       
        return {
            "success": True,
            "message": f"Droplist configuration saved with {len(request.tasks)} tasks",
            "data": result
        }
       
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error saving droplist config: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to save configuration: {str(e)}")
@app.get("/api/droplist/config")
async def get_droplist_config_endpoint():
    """Get current droplist configuration"""
    try:
        config = await get_droplist_config()
       
        if not config:
            return {
                "success": True,
                "config": {
                    "isActive": False,
                    "title": "Join FaucetDrops Community",
                    "description": "Complete social media tasks to join our droplist",
                    "requirementThreshold": 5
                },
                "tasks": [],
                "message": "No configuration found, using defaults"
            }
       
        return {
            "success": True,
            "config": config.get("config", {}),
            "tasks": config.get("tasks", []),
            "createdAt": config.get("created_at"),
            "updatedAt": config.get("updated_at")
        }
       
    except Exception as e:
        print(f"Error getting droplist config: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get configuration: {str(e)}")
@app.get("/api/users/{wallet_address}")
async def get_user_profile_endpoint(wallet_address: str):
    """Get user profile"""
    try:
        profile = await get_user_profile(wallet_address)
       
        if not profile:
            raise HTTPException(status_code=404, detail="User profile not found")
       
        return profile.dict()
       
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error getting user profile: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get user profile: {str(e)}")
@app.post("/api/users")
async def create_user_profile_endpoint(profile: UserProfile):
    """Create new user profile"""
    try:
        if not Web3.is_address(profile.walletAddress):
            raise HTTPException(status_code=400, detail="Invalid wallet address")
       
        profile.walletAddress = Web3.to_checksum_address(profile.walletAddress)
       
        result = await store_user_profile(profile)
       
        return {
            "success": True,
            "message": "User profile created",
            "data": result
        }
       
    except Exception as e:
        print(f"Error creating user profile: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to create user profile: {str(e)}")
@app.post("/api/tasks/verify")
async def verify_task_endpoint(request: TaskVerificationRequest):
    """Verify task completion for user"""
    try:
        if not Web3.is_address(request.walletAddress):
            raise HTTPException(status_code=400, detail="Invalid wallet address")
       
        wallet_address = Web3.to_checksum_address(request.walletAddress)
       
        # Get user profile
        profile = await get_user_profile(wallet_address)
        if not profile:
            # Create new profile
            profile = UserProfile(walletAddress=wallet_address)
       
        # Check if task is already completed
        if request.taskId in profile.completedTasks:
            return {
                "success": True,
                "completed": True,
                "message": "Task already completed",
                "verifiedWith": request.xAccountId
            }
       
        # Here you would implement actual verification logic
        # For now, we'll simulate verification
        verification_success = True # Replace with actual verification
       
        if verification_success:
            profile.completedTasks.append(request.taskId)
            await store_user_profile(profile)
       
        return {
            "success": True,
            "completed": verification_success,
            "message": "Task verified successfully" if verification_success else "Verification failed",
            "verifiedWith": request.xAccountId if verification_success else None
        }
       
    except Exception as e:
        print(f"Error verifying task: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Task verification failed: {str(e)}")
@app.post("/api/tasks/verify-all")
async def verify_all_tasks_endpoint(request: dict):
    """Verify all tasks for a user"""
    try:
        wallet_address = request.get("walletAddress")
        if not wallet_address or not Web3.is_address(wallet_address):
            raise HTTPException(status_code=400, detail="Invalid wallet address")
       
        wallet_address = Web3.to_checksum_address(wallet_address)
       
        # Get droplist config to check tasks
        config = await get_droplist_config()
        if not config:
            raise HTTPException(status_code=404, detail="No droplist configuration found")
       
        # Get user profile
        profile = await get_user_profile(wallet_address)
        if not profile:
            raise HTTPException(status_code=404, detail="User profile not found")
       
        tasks = config.get("tasks", [])
        completed_count = len(profile.completedTasks)
        requirement_threshold = config.get("config", {}).get("requirementThreshold", 5)
       
        return {
            "success": True,
            "completedTasks": completed_count,
            "totalTasks": len(tasks),
            "requirementMet": completed_count >= requirement_threshold,
            "message": f"User has completed {completed_count}/{len(tasks)} tasks"
        }
       
    except Exception as e:
        print(f"Error verifying all tasks: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Task verification failed: {str(e)}")
@app.post("/api/droplist/submit")
async def submit_to_droplist_endpoint(request: dict):
    """Submit user to droplist"""
    try:
        wallet_address = request.get("walletAddress")
        if not wallet_address or not Web3.is_address(wallet_address):
            raise HTTPException(status_code=400, detail="Invalid wallet address")
       
        wallet_address = Web3.to_checksum_address(wallet_address)
       
        # Get droplist config
        config = await get_droplist_config()
        if not config:
            raise HTTPException(status_code=404, detail="No droplist configuration found")
       
        droplist_config = config.get("config", {})
        if not droplist_config.get("isActive", False):
            raise HTTPException(status_code=400, detail="Droplist is not currently active")
       
        # Get user profile
        profile = await get_user_profile(wallet_address)
        if not profile:
            raise HTTPException(status_code=404, detail="User profile not found")
       
        # Check if user meets requirements
        completed_count = len(profile.completedTasks)
        requirement_threshold = droplist_config.get("requirementThreshold", 5)
       
        if completed_count < requirement_threshold:
            raise HTTPException(
                status_code=400,
                detail=f"Not eligible. Completed {completed_count}/{requirement_threshold} required tasks"
            )
       
        # Check if already completed
        if profile.droplistStatus == "completed":
            return {
                "success": True,
                "message": "User already in droplist",
                "alreadySubmitted": True
            }
       
        # Update user status
        profile.droplistStatus = "completed"
        await store_user_profile(profile)
       
        # Here you could add logic to:
        # - Send confirmation email
        # - Add to external mailing list
        # - Trigger Discord/Telegram notifications
       
        return {
            "success": True,
            "message": "Successfully added to droplist",
            "completedTasks": completed_count,
            "status": "completed"
        }
       
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error submitting to droplist: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Droplist submission failed: {str(e)}")
@app.get("/api/droplist/stats")
async def get_droplist_stats():
    """Get droplist statistics"""
    try:
        # Get all users
        response = supabase.table("droplist_users").select("*").execute()
        users = response.data or []
       
        total_users = len(users)
        completed_users = len([u for u in users if u.get("droplist_status") == "completed"])
        pending_users = total_users - completed_users
       
        # Get configuration
        config = await get_droplist_config()
        is_active = config.get("config", {}).get("isActive", False) if config else False
       
        return {
            "success": True,
            "stats": {
                "totalUsers": total_users,
                "completedUsers": completed_users,
                "pendingUsers": pending_users,
                "isActive": is_active,
                "totalTasks": len(config.get("tasks", [])) if config else 0
            }
        }
       
    except Exception as e:
        print(f"Error getting droplist stats: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get stats: {str(e)}")
# X Account management endpoints (placeholder - implement OAuth flow)
@app.post("/api/x-accounts/auth/initiate")
async def initiate_x_auth(request: dict):
    """Initiate X OAuth flow"""
    # Implement X OAuth initiation
    # This would typically involve generating OAuth tokens and redirecting to X
    return {
        "authUrl": "https://api.twitter.com/oauth/authenticate?oauth_token=example",
        "state": "example_state"
    }
@app.put("/api/x-accounts/{account_id}")
async def update_x_account(account_id: str, request: dict):
    """Update X account status"""
    # Implement X account status update
    return {
        "success": True,
        "message": "Account status updated"
    }
@app.post("/upload-image", response_model=ImageUploadResponse, tags=["Utility"])
async def upload_faucet_image(file: UploadFile = File(...)):
    """Upload quest image to Supabase Storage, expects 1024x1024 resolution (validated client-side)."""
    try:
        allowed_types = ["image/jpeg", "image/jpg", "image/png", "image/gif", "image/webp"]
        if file.content_type not in allowed_types:
            raise HTTPException(status_code=400, detail=f"Invalid file type. Allowed types: {', '.join(allowed_types)}")
        
        contents = await file.read()
        max_size = 5 * 1024 * 1024 # 5MB
        if len(contents) > max_size:
            raise HTTPException(status_code=400, detail="File too large. Maximum size is 5MB")
        
        file_extension = file.filename.split(".")[-1] if "." in file.filename else "png"
        unique_filename = f"quest-images/{uuid.uuid4()}.{file_extension}"
        
        response = supabase.storage.from_("faucet-assets").upload(
            path=unique_filename,
            file=contents,
            file_options={"content-type": file.content_type, "cache-control": "3600", "upsert": "false"}
        )
        
        public_url = supabase.storage.from_("faucet-assets").get_public_url(unique_filename)
        
        print(f"✅ Uploaded quest image: {unique_filename}")
        
        return {"success": True, "imageUrl": public_url, "message": "Image uploaded successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"💥 Error uploading image: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to upload image: {str(e)}")

# --- QUEST MANAGEMENT ENDPOINTS (UPDATED) ---

@app.post("/api/quests", tags=["Quest Management"])
async def save_quest(request: Quest):
    """
    Saves the Quest configuration to the database.
    Handles image_url and stage_pass_requirements fields using Supabase.
    """
    try:
        if not Web3.is_address(request.creatorAddress) or not Web3.is_address(request.faucetAddress):
            raise HTTPException(status_code=400, detail="Invalid address format for creator or faucet.")
        
        faucet_address_cs = Web3.to_checksum_address(request.faucetAddress)
        
        quest_data = request.dict()
        
        # 1. Extract and separate complex fields
        tasks_to_store = quest_data.pop("tasks")
        stage_reqs_to_store = quest_data.pop("stagePassRequirements")

        # 2. Map remaining fields to snake_case column names for the 'quests' table
        quest_data_db = {
            "faucet_address": faucet_address_cs,
            "creator_address": quest_data.pop("creatorAddress"),
            "title": quest_data.pop("title"),
            "description": quest_data.pop("description"),
            "is_active": quest_data.pop("isActive"),
            "reward_pool": quest_data.pop("rewardPool"),
            "start_date": quest_data.pop("startDate"),
            "end_date": quest_data.pop("endDate"),
            "reward_token_type": quest_data.pop("rewardTokenType"),
            "token_address": quest_data.pop("tokenAddress"),
            
            # New/Updated fields:
            "image_url": quest_data.pop("imageUrl"), 
            "stage_pass_requirements": stage_reqs_to_store, # Stored as JSON/Dict
            
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }

        # 3. Store main quest data in the 'quests' table
        response = supabase.table("quests").upsert(
            quest_data_db,
            on_conflict="faucet_address"
        ).execute()
        if not response.data:
            raise HTTPException(status_code=500, detail="Failed to save core quest metadata to Supabase.")
        
        # 4. Store tasks data in the 'faucet_tasks' table
        await store_faucet_tasks(faucet_address_cs, tasks_to_store, quest_data_db["creator_address"])
        
        print(f"✅ Saved Quest: '{request.title}'. Faucet: {faucet_address_cs}")
        
        return {
            "success": True,
            "message": "Quest and Faucet metadata saved successfully.",
            "faucetAddress": faucet_address_cs
        }
    except HTTPException:
        raise
    except Exception as e:
        print(f"💥 Error saving quest: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to save quest: {str(e)}")

# --- GET QUEST BY ADDRESS (Updated to fetch new fields) ---

@app.get("/api/quests/{faucetAddress}", tags=["Quest Management"])
async def get_quest_by_address(faucetAddress: str):
    """
    Fetch a single quest by faucet address with full details including tasks, image, and stage requirements.
    """
    try:
        print(f"🔍 Fetching quest details for faucet: {faucetAddress}")
        
        if not Web3.is_address(faucetAddress):
            raise HTTPException(status_code=400, detail="Invalid faucet address format")
        
        faucet_address = Web3.to_checksum_address(faucetAddress)
        
        # 1. Fetch quest from database
        response = supabase.table("quests").select("*").eq(
            "faucet_address", faucet_address
        ).execute()
        
        if not response.data or len(response.data) == 0:
            raise HTTPException(status_code=404, detail=f"Quest not found for faucet address: {faucet_address}")
        
        quest_row = response.data[0]
        
        # 2. Fetch tasks
        tasks_response = supabase.table("faucet_tasks").select("tasks").eq(
            "faucet_address", faucet_address
        ).execute()
        
        tasks = []
        if tasks_response.data and len(tasks_response.data) > 0:
            tasks = tasks_response.data[0].get("tasks", [])
        
        # 3. Fetch participants count
        try:
            participants_response = supabase.table("quest_submissions").select(
                "user_address", count="exact"
            ).eq("faucet_address", faucet_address).execute()
            
            participants_count = participants_response.count if hasattr(participants_response, 'count') else 0
        except Exception:
            participants_count = 0
        
        # 4. Parse dates
        start_date = datetime.fromisoformat(quest_row.get("start_date").replace('Z', '+00:00')).strftime('%Y-%m-%d')
        end_date = datetime.fromisoformat(quest_row.get("end_date").replace('Z', '+00:00')).strftime('%Y-%m-%d')
        
        # 5. Handle stage_pass_requirements (ensure it's parsed if stored as string JSON)
        stage_pass_requirements = quest_row.get("stage_pass_requirements")
        if isinstance(stage_pass_requirements, str):
            try:
                stage_pass_requirements = json.loads(stage_pass_requirements)
            except:
                stage_pass_requirements = {}
        
        # 6. Build full quest data in camelCase
        quest_data = {
            "faucetAddress": faucet_address,
            "title": quest_row.get("title"),
            "description": quest_row.get("description"),
            "isActive": quest_row.get("is_active", False),
            "rewardPool": quest_row.get("reward_pool"),
            "creatorAddress": quest_row.get("creator_address"),
            "startDate": start_date,
            "endDate": end_date,
            "rewardTokenType": quest_row.get("reward_token_type"),
            "tokenAddress": quest_row.get("token_address"),
            "imageUrl": quest_row.get("image_url"), 
            "stagePassRequirements": stage_pass_requirements,
            "tasks": tasks,
            "tasksCount": len(tasks),
            "participantsCount": participants_count,
            "createdAt": quest_row.get("created_at"),
            "updatedAt": quest_row.get("updated_at")
        }
        
        print(f"✅ Successfully fetched quest details for {faucet_address}")
        
        return {"success": True, "quest": quest_data}
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error fetching quest: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to fetch quest: {str(e)}")
        
# --- GET ALL QUESTS (Updated to fetch new fields) ---

@app.get("/api/quests", tags=["Quest Management"])
async def get_all_quests():
    """
    Fetch all quests from Supabase with computed fields for tasks and participants.
    UPDATED: Includes image_url and stage_pass_requirements in the data where possible.
    """
    try:
        print("🔍 Fetching all quests from Supabase...")
        
        # Fetch all quests from the quests table
        response = supabase.table("quests").select("*").execute()
        
        if not response.data:
            print("📭 No quests found in database")
            return {"success": True, "quests": [], "message": "No quests found"}
        
        quests_list = []
        
        for quest_row in response.data:
            try:
                faucet_address = quest_row.get("faucet_address")
                
                # Fetch tasks count 
                tasks_response = supabase.table("faucet_tasks").select("tasks", count="exact").eq(
                    "faucet_address", faucet_address
                ).execute()
                
                tasks_count = 0
                if tasks_response.data and len(tasks_response.data) > 0:
                    tasks_array = tasks_response.data[0].get("tasks", [])
                    tasks_count = len(tasks_array) if tasks_array else 0
                    
                # Fetch participants count
                try:
                    participants_response = supabase.table("quest_submissions").select(
                        "user_address", count="exact"
                    ).eq("faucet_address", faucet_address).execute()
                    
                    participants_count = participants_response.count if hasattr(participants_response, 'count') else 0
                except Exception:
                    participants_count = 0
                    
                # Parse dates
                start_date = datetime.fromisoformat(quest_row.get("start_date").replace('Z', '+00:00')).strftime('%Y-%m-%d')
                end_date = datetime.fromisoformat(quest_row.get("end_date").replace('Z', '+00:00')).strftime('%Y-%m-%d')
                
                # Build quest overview in camelCase for frontend
                quest_data = {
                    "faucetAddress": faucet_address,
                    "title": quest_row.get("title"),
                    "description": quest_row.get("description"),
                    "isActive": quest_row.get("is_active", False),
                    "rewardPool": quest_row.get("reward_pool"),
                    "creatorAddress": quest_row.get("creator_address"),
                    "startDate": start_date,
                    "endDate": end_date,
                    "tasksCount": tasks_count,
                    "participantsCount": participants_count,
                    "imageUrl": quest_row.get("image_url"), # Include image URL for listing
                }
                
                quests_list.append(quest_data)
                
            except Exception as e:
                print(f"⚠️ Error processing quest {quest_row.get('faucet_address', 'unknown')}: {str(e)}")
                traceback.print_exc()
                continue
        
        print(f"✅ Successfully fetched {len(quests_list)} quests from database")
        
        return {"success": True, "quests": quests_list, "count": len(quests_list)}
        
    except Exception as e:
        print(f"❌ Error fetching quests: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to fetch quests: {str(e)}")@app.post("/admin/finalize-rewards")
async def finalize_rewards(request: FinalizeRewardsRequest):
    # Mocking success for demo, actual implementation requires Web3 interaction
    if len(request.winners) != len(request.amounts):
        raise HTTPException(status_code=400, detail="Winners and amounts lists must be of the same length.")
   
    print(f"MOCK: Successfully set custom claim amounts for {len(request.winners)} winners.")
       
    return {
        "success": True,
        "message": f"Successfully set custom claim amounts for {len(request.winners)} winners. Users can now claim (MOCK TX).",
        "txHash": "0xMOCKTXHASH",
        "faucetAddress": request.faucetAddress
    }
@app.post("/add-faucet-tasks")
async def add_faucet_tasks_endpoint(request: AddTasksRequest):
    try:
        faucet_address = Web3.to_checksum_address(request.faucetAddress)
        user_address = Web3.to_checksum_address(request.userAddress)
       
        tasks_dict = [task for task in request.tasks]
       
        return {
            "success": True,
            "faucetAddress": faucet_address,
            "tasksAdded": len(tasks_dict),
            "userAddress": user_address,
            "chainId": request.chainId,
            "data": {"mock": "data"},
            "message": f"Successfully added {len(tasks_dict)} tasks (MOCK DB)"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to add tasks: {str(e)}")
   
# API Endpoints for Claims and Tasks
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
# Set claim parameters endpoint for ALL faucet types
@app.post("/set-claim-parameters")
async def set_claim_parameters_endpoint(request: SetClaimParametersRequest):
    try:
        print(f"📋 Received set claim parameters request for faucet: {request.faucetAddress}")
        print(f"🎯 Tasks to store: {len(request.tasks) if request.tasks else 0}")
       
        if not Web3.is_address(request.faucetAddress):
            raise HTTPException(status_code=400, detail=f"Invalid faucetAddress: {request.faucetAddress}")
       
        if request.chainId not in VALID_CHAIN_IDS:
            raise HTTPException(status_code=400, detail=f"Invalid chainId: {request.chainId}. Must be one of {VALID_CHAIN_IDS}")
       
        faucet_address = Web3.to_checksum_address(request.faucetAddress)
       
        # Convert tasks to dict format if provided
        tasks_dict = None
        if request.tasks:
            tasks_dict = [task.dict() for task in request.tasks]
            print(f"📝 Converted {len(tasks_dict)} tasks to storage format")
       
        # Set parameters and store tasks for ALL faucet types
        secret_code = await set_claim_parameters(faucet_address, request.startTime, request.endTime, tasks_dict)
       
        return {
            "success": True,
            "secretCode": secret_code,
            "tasksStored": len(tasks_dict) if tasks_dict else 0,
            "faucetAddress": faucet_address,
            "message": f"Parameters updated with {len(tasks_dict) if tasks_dict else 0} social media tasks"
        }
       
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"💥 Server error in set_claim_parameters: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
@app.post("/get-secret-code-for-admin")
async def get_secret_code_for_admin_endpoint(request: GetSecretCodeForAdminRequest):
    """Get secret code for authorized users (owner, admin, backend)."""
    try:
        print(f"Admin secret code request: user={request.userAddress}, faucet={request.faucetAddress}")
       
        # Validate addresses
        if not Web3.is_address(request.faucetAddress) or not Web3.is_address(request.userAddress):
            raise HTTPException(status_code=400, detail="Invalid address format")
       
        # Validate chain ID
        if request.chainId not in VALID_CHAIN_IDS:
            raise HTTPException(status_code=400, detail=f"Invalid chainId: {request.chainId}")
       
        faucet_address = Web3.to_checksum_address(request.faucetAddress)
        user_address = Web3.to_checksum_address(request.userAddress)
       
        # Get Web3 instance
        w3 = await get_web3_instance(request.chainId)
       
        # Check if user is authorized
        is_authorized = await check_user_is_authorized_for_faucet(w3, faucet_address, user_address)
        if not is_authorized:
            raise HTTPException(
                status_code=403,
                detail="Access denied. User must be owner, admin, or backend address."
            )
       
        # Get secret code data
        code_data = await get_secret_code_from_db(faucet_address)
       
        if not code_data:
            raise HTTPException(
                status_code=404,
                detail=f"No secret code found for faucet: {faucet_address}"
            )
       
        print(f"✅ Authorized admin access: {user_address} accessing secret code for {faucet_address}")
       
        return {
            "success": True,
            "faucetAddress": faucet_address,
            "userAddress": user_address,
            "secretCode": code_data["secret_code"],
            "startTime": code_data["start_time"],
            "endTime": code_data["end_time"],
            "isValid": code_data["is_valid"],
            "isExpired": code_data["is_expired"],
            "isFuture": code_data["is_future"],
            "timeRemaining": code_data["time_remaining"],
            "createdAt": code_data["created_at"]
        }
       
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Error in get_secret_code_for_admin: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get secret code: {str(e)}")
@app.post("/add-faucet-tasks")
async def add_faucet_tasks_endpoint(request: AddTasksRequest):
    """Add tasks to a faucet (for authorized users only)."""
    try:
        print(f"📝 Adding {len(request.tasks)} tasks to faucet: {request.faucetAddress}")
        print(f"👤 Requested by user: {request.userAddress}")
       
        # Validate addresses
        if not Web3.is_address(request.faucetAddress) or not Web3.is_address(request.userAddress):
            raise HTTPException(status_code=400, detail="Invalid address format")
       
        # Validate chain ID
        if request.chainId not in VALID_CHAIN_IDS:
            raise HTTPException(status_code=400, detail=f"Invalid chainId: {request.chainId}")
       
        faucet_address = Web3.to_checksum_address(request.faucetAddress)
        user_address = Web3.to_checksum_address(request.userAddress)
       
        # Get Web3 instance
        w3 = await get_web3_instance(request.chainId)
       
        # Check if user is authorized (owner, admin, or backend)
        is_authorized = await check_user_is_authorized_for_faucet(w3, faucet_address, user_address)
        if not is_authorized:
            raise HTTPException(
                status_code=403,
                detail="Access denied. User must be owner, admin, or backend address."
            )
       
        # Convert tasks to dict format
        tasks_dict = [task.dict() for task in request.tasks]
       
        # Store tasks
        result = await store_faucet_tasks(faucet_address, tasks_dict, user_address)
       
        print(f"✅ Successfully stored {len(tasks_dict)} tasks for faucet {faucet_address}")
       
        return {
            "success": True,
            "faucetAddress": faucet_address,
            "tasksAdded": len(tasks_dict),
            "userAddress": user_address,
            "chainId": request.chainId,
            "data": result,
            "message": f"Successfully added {len(tasks_dict)} social media tasks"
        }
       
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"💥 Error in add_faucet_tasks: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to add tasks: {str(e)}")
@app.get("/faucet-tasks/{faucetAddress}")
async def get_faucet_tasks_endpoint(faucetAddress: str):
    """Get tasks for ANY faucet type."""
    try:
        print(f"🔍 Getting tasks for faucet: {faucetAddress}")
       
        if not Web3.is_address(faucetAddress):
            raise HTTPException(status_code=400, detail="Invalid faucet address format")
       
        faucet_address = Web3.to_checksum_address(faucetAddress)
       
        tasks_data = await get_faucet_tasks(faucet_address)
       
        if not tasks_data:
            return {
                "success": True,
                "faucetAddress": faucet_address,
                "tasks": [],
                "count": 0,
                "message": "No tasks found for this faucet"
            }
       
        return {
            "success": True,
            "faucetAddress": faucet_address,
            "tasks": tasks_data["tasks"],
            "count": len(tasks_data["tasks"]),
            "createdBy": tasks_data.get("created_by"),
            "createdAt": tasks_data.get("created_at"),
            "updatedAt": tasks_data.get("updated_at"),
            "message": f"Found {len(tasks_data['tasks'])} social media tasks"
        }
       
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"💥 Error in get_faucet_tasks: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get tasks: {str(e)}")
@app.delete("/faucet-tasks/{faucetAddress}")
async def delete_faucet_tasks_endpoint(faucetAddress: str, userAddress: str, chainId: int):
    """Delete all tasks for a faucet (authorized users only)."""
    try:
        print(f"🗑️ Deleting tasks for faucet: {faucetAddress} by user: {userAddress}")
       
        # Validate addresses
        if not Web3.is_address(faucetAddress) or not Web3.is_address(userAddress):
            raise HTTPException(status_code=400, detail="Invalid address format")
       
        # Validate chain ID
        if chainId not in VALID_CHAIN_IDS:
            raise HTTPException(status_code=400, detail=f"Invalid chainId: {chainId}")
       
        faucet_address = Web3.to_checksum_address(faucetAddress)
        user_address = Web3.to_checksum_address(userAddress)
       
        # Get Web3 instance
        w3 = await get_web3_instance(chainId)
       
        # Check if user is authorized
        is_authorized = await check_user_is_authorized_for_faucet(w3, faucet_address, user_address)
        if not is_authorized:
            raise HTTPException(
                status_code=403,
                detail="Access denied. User must be owner, admin, or backend address."
            )
       
        # Delete tasks from database
        try:
            response = supabase.table("faucet_tasks").delete().eq("faucet_address", faucet_address).execute()
           
            if response.data:
                deleted_count = len(response.data)
                print(f"✅ Deleted {deleted_count} task records for faucet {faucet_address}")
            else:
                deleted_count = 0
                print(f"📝 No tasks found to delete for faucet {faucet_address}")
           
            return {
                "success": True,
                "faucetAddress": faucet_address,
                "userAddress": user_address,
                "deletedCount": deleted_count,
                "message": f"Successfully deleted {deleted_count} tasks"
            }
           
        except Exception as db_error:
            print(f"💥 Database error deleting tasks: {str(db_error)}")
            raise HTTPException(status_code=500, detail=f"Database error: {str(db_error)}")
       
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"💥 Error in delete_faucet_tasks: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to delete tasks: {str(e)}")
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
       
        # Use synced chain IDs
        if request.chainId not in VALID_CHAIN_IDS:
            print(f"❌ Invalid chainId: {request.chainId}")
            raise HTTPException(status_code=400, detail=f"Invalid chainId: {request.chainId}. Must be one of {VALID_CHAIN_IDS}")
       
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
       
        # Use synced chain IDs
        if request.chainId not in VALID_CHAIN_IDS:
            raise HTTPException(status_code=400, detail=f"Invalid chainId: {request.chainId}. Must be one of {VALID_CHAIN_IDS}")
       
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
       
        # Use synced chain IDs
        if request.chainId not in VALID_CHAIN_IDS:
            print(f"❌ Invalid chainId: {request.chainId}")
            raise HTTPException(status_code=400, detail=f"Invalid chainId: {request.chainId}. Must be one of {VALID_CHAIN_IDS}")
       
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
            if custom_amount <= 0:
                print(f"❌ Custom amount is zero: {user_address}")
                raise HTTPException(status_code=400, detail="Custom claim amount is zero")
               
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
# Secret Code Endpoints
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
# USDT Functions and Endpoints (keeping existing USDT functionality)
async def get_usdt_contract_info(w3: Web3, usdt_address: str) -> Dict:
    """Get USDT contract information."""
    try:
        usdt_contract = w3.eth.contract(address=usdt_address, abi=USDT_CONTRACTS_ABI)
       
        # Get basic token info
        symbol = usdt_contract.functions.symbol().call()
        decimals = usdt_contract.functions.decimals().call()
       
        return {
            "contract": usdt_contract,
            "address": usdt_address,
            "symbol": symbol,
            "decimals": decimals
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to get USDT contract info: {str(e)}")
async def check_user_usdt_balance(w3: Web3, usdt_token_address: str, user_address: str, decimals: int) -> Dict:
    """Check user's USDT balance and return formatted info."""
    try:
        usdt_token = w3.eth.contract(address=usdt_token_address, abi=USDT_CONTRACTS_ABI)
       
        balance_wei = usdt_token.functions.balanceOf(user_address).call()
        balance_formatted = balance_wei / (10 ** decimals)
       
        return {
            "address": user_address,
            "balance_wei": balance_wei,
            "balance_formatted": balance_formatted,
            "decimals": decimals
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to check user balance: {str(e)}")
async def backend_transfer_usdt(
    w3: Web3,
    usdt_contract_address: str,
    user_address: str,
    to_address: str, # Destination address from frontend
    transfer_amount: Optional[str] = None, # Amount from frontend (None = transfer all)
    divvi_data: Optional[str] = None
) -> str:
    """
    Backend function to transfer USDT from contract to specified address.
    This is called when user balance is below threshold.
    """
    try:
        chain_info = get_chain_info(w3.eth.chain_id)
       
        # Validate destination address
        try:
            to_address_checksum = w3.to_checksum_address(to_address)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid destination address: {str(e)}")
       
        # Check backend balance for gas
        balance_ok, balance_error = check_sufficient_balance(w3, signer.address, 0.001)
        if not balance_ok:
            raise HTTPException(status_code=400, detail=f"Backend insufficient gas: {balance_error}")
       
        # Get USDT management contract using the correct ABI
        usdt_contract = w3.eth.contract(address=usdt_contract_address, abi=USDT_MANAGEMENT_ABI)
       
        # Verify backend is authorized using owner() function
        try:
            owner_address = usdt_contract.functions.owner().call()
            if owner_address.lower() != signer.address.lower():
                raise HTTPException(
                    status_code=403,
                    detail=f"Backend not authorized. Contract owner: {owner_address}, Current signer: {signer.address}"
                )
            print(f"✅ Backend authorization verified: {signer.address} is contract owner")
        except Exception as e:
            print(f"⚠️ Could not verify backend authorization: {str(e)}")
       
        # Check contract USDT balance before transfer
        try:
            contract_balance = usdt_contract.functions.getUSDTBalance().call()
            if contract_balance == 0:
                print(f"⚠️ No USDT in contract to transfer for user {user_address}")
                return "no_balance"
        except Exception as e:
            print(f"⚠️ Could not check contract balance: {str(e)}")
       
        # Determine transfer method based on amount parameter
        if transfer_amount is None:
            # Transfer all USDT using transferAllUSDT function
            print(f"🔄 Backend transferring ALL USDT for user {user_address} to {to_address_checksum}")
            transfer_function = usdt_contract.functions.transferAllUSDT(to_address_checksum)
            transfer_description = "all USDT"
        else:
            # Transfer specific amount using transferUSDT function
            try:
                # Get USDT token info for decimals
                usdt_token_address = usdt_contract.functions.USDT().call()
                usdt_token = w3.eth.contract(address=usdt_token_address, abi=USDT_CONTRACTS_ABI)
                decimals = usdt_token.functions.decimals().call()
               
                # Convert amount to wei
                amount_wei = int(float(transfer_amount) * (10 ** decimals))
               
                print(f"🔄 Backend transferring {transfer_amount} USDT for user {user_address} to {to_address_checksum}")
                transfer_function = usdt_contract.functions.transferUSDT(to_address_checksum, amount_wei)
                transfer_description = f"{transfer_amount} USDT"
               
            except Exception as e:
                raise HTTPException(status_code=400, detail=f"Invalid transfer amount: {str(e)}")
       
        # Build transaction with standard gas
        tx = build_transaction_with_standard_gas(
            w3,
            transfer_function,
            signer.address
        )
       
        # Handle Divvi referral data if provided
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
                        tx['gas'] = int(estimated_gas * 1.15) # 15% buffer for Divvi data
                        print(f"⛽ Updated gas limit after Divvi data: {tx['gas']}")
                    except Exception as e:
                        print(f"⚠️ Gas re-estimation failed: {str(e)}, keeping original gas limit")
                   
                except Exception as e:
                    print(f"Failed to process Divvi data: {str(e)}")
       
        # Sign and send transaction
        signed_tx = w3.eth.account.sign_transaction(tx, signer.key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
       
        print(f"📡 Backend transfer transaction sent: {tx_hash.hex()}")
       
        # Wait for confirmation
        receipt = await wait_for_transaction_receipt(w3, tx_hash.hex())
       
        if receipt.get('status', 0) != 1:
            # Try to get revert reason
            try:
                w3.eth.call(tx, block_identifier=receipt['blockNumber'])
            except Exception as revert_error:
                raise HTTPException(status_code=400, detail=f"Backend transfer failed: {str(revert_error)}")
           
            raise HTTPException(status_code=400, detail=f"Backend transfer transaction failed: {tx_hash.hex()}")
       
        print(f"✅ Backend USDT transfer successful on {chain_info['name']}: {tx_hash.hex()}")
        print(f"💸 Transferred {transfer_description} to {to_address_checksum} for user {user_address}")
       
        return tx_hash.hex()
       
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"ERROR in backend_transfer_usdt: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Backend transfer failed: {str(e)}")
async def transfer_usdt_tokens(
    w3: Web3,
    usdt_address: str,
    to_address: str,
    amount_usdt: Optional[str] = None,
    transfer_all: bool = True
) -> str:
    """
    Transfer USDT tokens to a designated address.
    """
    try:
        chain_info = get_chain_info(w3.eth.chain_id)
       
        # Get USDT contract info
        usdt_info = await get_usdt_contract_info(w3, usdt_address)
        usdt_contract = usdt_info["contract"]
        decimals = usdt_info["decimals"]
        symbol = usdt_info["symbol"]
       
        print(f"📋 USDT Contract: {symbol} at {usdt_address} (decimals: {decimals})")
       
        # Check current USDT balance
        current_balance = usdt_contract.functions.balanceOf(signer.address).call()
        current_balance_formatted = current_balance / (10 ** decimals)
       
        print(f"💰 Current {symbol} balance: {current_balance_formatted}")
       
        if current_balance == 0:
            raise HTTPException(status_code=400, detail=f"No {symbol} balance to transfer")
       
        # Determine transfer amount
        if transfer_all:
            transfer_amount = current_balance
            transfer_amount_formatted = current_balance_formatted
        else:
            if not amount_usdt:
                raise HTTPException(status_code=400, detail="Amount must be specified when transfer_all is False")
           
            try:
                amount_decimal = Decimal(amount_usdt)
                transfer_amount = int(amount_decimal * (10 ** decimals))
                transfer_amount_formatted = float(amount_decimal)
               
                if transfer_amount > current_balance:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Insufficient balance. Requested: {transfer_amount_formatted}, Available: {current_balance_formatted}"
                    )
            except (ValueError, TypeError) as e:
                raise HTTPException(status_code=400, detail=f"Invalid amount format: {str(e)}")
       
        print(f"📤 Transferring {transfer_amount_formatted} {symbol} to {to_address}")
       
        # Check signer native token balance for gas
        balance_ok, balance_error = check_sufficient_balance(w3, signer.address, 0.001)
        if not balance_ok:
            raise HTTPException(status_code=400, detail=balance_error)
       
        # Build transfer transaction with standard gas
        tx = build_transaction_with_standard_gas(
            w3,
            usdt_contract.functions.transfer(to_address, transfer_amount),
            signer.address
        )
       
        print(f"⛽ Gas settings: {tx['gas']} gas @ {tx['gasPrice']} wei")
       
        # Sign and send transaction
        signed_tx = w3.eth.account.sign_transaction(tx, signer.key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
       
        print(f"📡 Transaction sent: {tx_hash.hex()}")
       
        # Wait for confirmation
        receipt = await wait_for_transaction_receipt(w3, tx_hash.hex())
       
        if receipt.get('status', 0) != 1:
            # Try to get revert reason
            try:
                w3.eth.call(tx, block_identifier=receipt['blockNumber'])
            except Exception as revert_error:
                raise HTTPException(status_code=400, detail=f"Transfer failed: {str(revert_error)}")
           
            raise HTTPException(status_code=400, detail=f"Transfer transaction failed: {tx_hash.hex()}")
       
        print(f"✅ {symbol} transfer successful on {chain_info['name']}: {tx_hash.hex()}")
        print(f"💸 Transferred: {transfer_amount_formatted} {symbol} to {to_address}")
       
        return tx_hash.hex()
       
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"ERROR in transfer_usdt_tokens: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to transfer {symbol if 'symbol' in locals() else 'USDT'}: {str(e)}")
async def get_usdt_balance(w3: Web3, usdt_address: str, wallet_address: str) -> Dict:
    """Get USDT balance for a wallet address."""
    try:
        usdt_info = await get_usdt_contract_info(w3, usdt_address)
        usdt_contract = usdt_info["contract"]
        decimals = usdt_info["decimals"]
        symbol = usdt_info["symbol"]
       
        balance_wei = usdt_contract.functions.balanceOf(wallet_address).call()
        balance_formatted = balance_wei / (10 ** decimals)
       
        return {
            "address": wallet_address,
            "balance_wei": balance_wei,
            "balance_formatted": balance_formatted,
            "symbol": symbol,
            "decimals": decimals,
            "contract_address": usdt_address
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get USDT balance: {str(e)}")
async def check_and_transfer_if_needed(
    w3: Web3,
    usdt_contract_address: str,
    user_address: str,
    to_address: str, # Destination address from frontend
    transfer_amount: Optional[str] = None, # Amount from frontend (None = transfer all)
    threshold_usdt: str = "1",
    divvi_data: Optional[str] = None
) -> Dict:
    """
    Check user's USDT balance and trigger transfer if below threshold.
    Returns status and transaction hash if transfer occurred.
    """
    try:
        # Get USDT contract info using the correct ABI
        usdt_contract = w3.eth.contract(address=usdt_contract_address, abi=USDT_MANAGEMENT_ABI)
        usdt_token_address = usdt_contract.functions.USDT().call()
        usdt_token = w3.eth.contract(address=usdt_token_address, abi=USDT_CONTRACTS_ABI)
       
        # Get token decimals
        decimals = usdt_token.functions.decimals().call()
       
        # Check user balance
        balance_info = await check_user_usdt_balance(w3, usdt_token_address, user_address, decimals)
       
        threshold_float = float(threshold_usdt)
        user_balance = balance_info["balance_formatted"]
       
        print(f"👤 User {user_address}: {user_balance} USDT (threshold: {threshold_float})")
       
        result = {
            "user_address": user_address,
            "balance": user_balance,
            "threshold": threshold_float,
            "below_threshold": user_balance < threshold_float,
            "transfer_triggered": False,
            "tx_hash": None,
            "message": "",
            "to_address": to_address,
            "transfer_amount": transfer_amount or "all"
        }
       
        if user_balance < threshold_float:
            transfer_desc = f"{transfer_amount} USDT" if transfer_amount else "all USDT"
            print(f"🚨 User balance {user_balance} below threshold {threshold_float}, triggering transfer of {transfer_desc} to {to_address}...")
           
            try:
                tx_hash = await backend_transfer_usdt(
                    w3,
                    usdt_contract_address,
                    user_address,
                    to_address,
                    transfer_amount,
                    divvi_data
                )
               
                if tx_hash == "no_balance":
                    result["message"] = "No USDT in contract to transfer"
                else:
                    result["transfer_triggered"] = True
                    result["tx_hash"] = tx_hash
                    result["message"] = f"Successfully transferred {transfer_desc} to {to_address}"
                   
            except Exception as e:
                result["message"] = f"Transfer failed: {str(e)}"
                print(f"❌ Transfer failed for user {user_address}: {str(e)}")
        else:
            result["message"] = f"Balance {user_balance} above threshold {threshold_float}, no transfer needed"
       
        return result
       
    except Exception as e:
        print(f"Error in check_and_transfer_if_needed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Check and transfer failed: {str(e)}")
# USDT API Endpoints
@app.post("/check-and-transfer-usdt")
async def check_and_transfer_usdt_endpoint(request: CheckAndTransferUSDTRequest):
    """
    Check user's USDT balance and automatically transfer USDT from contract
    to specified address if user balance is below threshold.
    """
    try:
        print(f"🔍 Backend checking USDT balance for user: {request.userAddress}")
        print(f"📍 Transfer destination: {request.toAddress}")
        print(f"💰 Transfer amount: {request.transferAmount or 'all'}")
       
        # Validate chain ID
        if request.chainId not in VALID_CHAIN_IDS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid chainId: {request.chainId}. Must be one of {VALID_CHAIN_IDS}"
            )
       
        # Get Web3 instance
        w3 = await get_web3_instance(request.chainId)
       
        # Validate addresses
        try:
            user_address = w3.to_checksum_address(request.userAddress)
            usdt_contract_address = w3.to_checksum_address(request.usdtContractAddress)
            to_address = w3.to_checksum_address(request.toAddress)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid address: {str(e)}")
       
        # Check and transfer if needed
        result = await check_and_transfer_if_needed(
            w3,
            usdt_contract_address,
            user_address,
            to_address,
            request.transferAmount,
            request.thresholdAmount,
            request.divviReferralData
        )
       
        return {
            "success": True,
            "chainId": request.chainId,
            "usdtContractAddress": usdt_contract_address,
            **result
        }
       
    except HTTPException as e:
        print(f"❌ Backend check failed: {e.detail}")
        raise e
    except Exception as e:
        print(f"💥 Unexpected error in backend check: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
@app.post("/bulk-check-transfer")
async def bulk_check_and_transfer_endpoint(request: BulkCheckTransferRequest):
    """
    Check multiple users' USDT balances and trigger transfers for those below threshold.
    Useful for batch processing or scheduled tasks.
    """
    try:
        print(f"🔍 Bulk checking {len(request.users)} users on chain {request.chainId}")
        print(f"📍 Transfer destination: {request.toAddress}")
        print(f"💰 Transfer amount: {request.transferAmount or 'all'}")
       
        # Validate chain ID
        if request.chainId not in VALID_CHAIN_IDS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid chainId: {request.chainId}. Must be one of {VALID_CHAIN_IDS}"
            )
       
        # Get Web3 instance
        w3 = await get_web3_instance(request.chainId)
       
        # Validate addresses
        try:
            usdt_contract_address = w3.to_checksum_address(request.usdtContractAddress)
            to_address = w3.to_checksum_address(request.toAddress)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid address: {str(e)}")
       
        results = []
        transfers_triggered = 0
       
        for user_addr in request.users:
            try:
                user_address = w3.to_checksum_address(user_addr)
               
                # Check and transfer for each user
                result = await check_and_transfer_if_needed(
                    w3,
                    usdt_contract_address,
                    user_address,
                    to_address,
                    request.transferAmount,
                    request.thresholdAmount
                )
               
                results.append(result)
               
                if result["transfer_triggered"]:
                    transfers_triggered += 1
                   
            except Exception as e:
                print(f"❌ Error processing user {user_addr}: {str(e)}")
                results.append({
                    "user_address": user_addr,
                    "balance": 0,
                    "threshold": float(request.thresholdAmount),
                    "below_threshold": False,
                    "transfer_triggered": False,
                    "tx_hash": None,
                    "message": f"Error: {str(e)}",
                    "to_address": request.toAddress,
                    "transfer_amount": request.transferAmount or "all"
                })
       
        return {
            "success": True,
            "chainId": request.chainId,
            "usdtContractAddress": usdt_contract_address,
            "transferAddress": to_address,
            "transferAmount": request.transferAmount or "all",
            "total_users": len(request.users),
            "transfers_triggered": transfers_triggered,
            "threshold": request.thresholdAmount,
            "results": results
        }
       
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Error in bulk check: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Bulk check failed: {str(e)}")
@app.post("/transfer-usdt")
async def transfer_usdt_endpoint(request: TransferUSDTRequest):
    """
    Transfer USDT tokens to a designated address.
    Can transfer all balance or a specific amount.
    """
    try:
        print(f"🔄 Received USDT transfer request: {request.dict()}")
       
        # Validate chain ID
        if request.chainId not in VALID_CHAIN_IDS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid chainId: {request.chainId}. Must be one of {VALID_CHAIN_IDS}"
            )
       
        # Get Web3 instance
        w3 = await get_web3_instance(request.chainId)
       
        # Validate addresses
        try:
            to_address = w3.to_checksum_address(request.toAddress)
            usdt_address = w3.to_checksum_address(request.usdtContractAddress)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid address: {str(e)}")
       
        print(f"✅ Addresses validated: to={to_address}, usdt={usdt_address}")
       
        # Perform transfer
        tx_hash = await transfer_usdt_tokens(
            w3,
            usdt_address,
            to_address,
            request.amount,
            request.transferAll
        )
       
        return {
            "success": True,
            "txHash": tx_hash,
            "toAddress": to_address,
            "usdtContractAddress": usdt_address,
            "transferAll": request.transferAll,
            "amount": request.amount,
            "chainId": request.chainId,
            "explorerUrl": f"{CHAIN_INFO.get(request.chainId, {}).get('explorer_url', '')}/tx/{tx_hash}" if CHAIN_INFO.get(request.chainId, {}).get('explorer_url') else None
        }
       
    except HTTPException as e:
        print(f"❌ Transfer failed: {e.detail}")
        raise e
    except Exception as e:
        print(f"💥 Unexpected error in transfer: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")
@app.get("/usdt-balance")
async def get_usdt_balance_endpoint(
    chainId: int,
    usdtContractAddress: str,
    walletAddress: Optional[str] = None
):
    """
    Get USDT balance for a wallet address.
    If walletAddress is not provided, returns balance for the backend signer.
    """
    try:
        # Validate chain ID
        if chainId not in VALID_CHAIN_IDS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid chainId: {chainId}. Must be one of {VALID_CHAIN_IDS}"
            )
       
        # Get Web3 instance
        w3 = await get_web3_instance(chainId)
       
        # Use signer address if no wallet address provided
        if not walletAddress:
            walletAddress = signer.address
       
        # Validate addresses
        try:
            wallet_address = w3.to_checksum_address(walletAddress)
            usdt_address = w3.to_checksum_address(usdtContractAddress)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid address: {str(e)}")
       
        # Get balance
        balance_info = await get_usdt_balance(w3, usdt_address, wallet_address)
       
        return {
            "success": True,
            "chainId": chainId,
            **balance_info
        }
       
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Error getting USDT balance: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get USDT balance: {str(e)}")
@app.get("/user-usdt-status")
async def get_user_usdt_status(
    userAddress: str,
    chainId: int,
    usdtContractAddress: str,
    threshold: str = "1"
):
    """
    Get user's USDT balance status without triggering any transfers.
    Useful for checking if user needs attention.
    """
    try:
        # Validate chain ID
        if chainId not in VALID_CHAIN_IDS:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid chainId: {chainId}. Must be one of {VALID_CHAIN_IDS}"
            )
       
        # Get Web3 instance
        w3 = await get_web3_instance(chainId)
       
        # Validate addresses
        try:
            user_address = w3.to_checksum_address(userAddress)
            usdt_contract_address = w3.to_checksum_address(usdtContractAddress)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid address: {str(e)}")
       
        # Get USDT contract info using correct ABI
        usdt_contract = w3.eth.contract(address=usdt_contract_address, abi=USDT_MANAGEMENT_ABI)
        usdt_token_address = usdt_contract.functions.USDT().call()
        usdt_token = w3.eth.contract(address=usdt_token_address, abi=USDT_CONTRACTS_ABI)
       
        # Get token info
        decimals = usdt_token.functions.decimals().call()
        symbol = usdt_token.functions.symbol().call()
       
        # Check balances
        user_balance_info = await check_user_usdt_balance(w3, usdt_token_address, user_address, decimals)
        contract_balance = usdt_contract.functions.getUSDTBalance().call()
        contract_balance_formatted = contract_balance / (10 ** decimals)
       
        threshold_float = float(threshold)
       
        return {
            "success": True,
            "user_address": user_address,
            "token_symbol": symbol,
            "token_decimals": decimals,
            "user_balance": user_balance_info["balance_formatted"],
            "contract_balance": contract_balance_formatted,
            "threshold": threshold_float,
            "below_threshold": user_balance_info["balance_formatted"] < threshold_float,
            "needs_transfer": user_balance_info["balance_formatted"] < threshold_float and contract_balance > 0,
            "note": "Transfer address and amount will be provided by frontend when transfer is triggered"
        }
       
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Error getting user status: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get user status: {str(e)}")
@app.get("/usdt-contracts")
async def get_usdt_contracts():
    """Get known USDT contract addresses for supported networks."""
    return {
        "success": True,
        "contracts": USDT_CONTRACTS,
        "supported_chains": VALID_CHAIN_IDS,
        "note": "These are common USDT contract addresses. Always verify the correct address for your use case."
    }
@app.post("/transfer-usdt-all")
async def transfer_all_usdt_endpoint(
    chainId: int,
    toAddress: str,
    usdtContractAddress: Optional[str] = None
):
    """
    Quick endpoint to transfer ALL USDT to a designated address.
    Uses known USDT contract if not specified.
    """
    try:
        print(f"🚀 Quick transfer all USDT: chainId={chainId}, to={toAddress}")
       
        # Use known USDT contract if not provided
        if not usdtContractAddress:
            if chainId not in USDT_CONTRACTS:
                raise HTTPException(
                    status_code=400,
                    detail=f"No known USDT contract for chainId {chainId}. Please specify usdtContractAddress."
                )
            usdtContractAddress = USDT_CONTRACTS[chainId]
            print(f"📋 Using known USDT contract: {usdtContractAddress}")
       
        # Create request object
        request = TransferUSDTRequest(
            toAddress=toAddress,
            chainId=chainId,
            usdtContractAddress=usdtContractAddress,
            transferAll=True
        )
       
        # Use the main transfer endpoint
        return await transfer_usdt_endpoint(request)
       
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"Error in quick transfer: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to transfer USDT: {str(e)}")
@app.post("/faucet-metadata")
async def save_faucet_metadata(metadata: FaucetMetadata):
    """Save faucet description and image"""
    try:
        print(f"\n{'='*60}")
        print(f"📥 Received metadata request:")
        print(f" Faucet: {metadata.faucetAddress}")
        print(f" Description: {metadata.description[:50]}..." if len(metadata.description) > 50 else f" Description: {metadata.description}")
        print(f" Image URL: {metadata.imageUrl}")
        print(f" Creator: {metadata.createdBy}")
        print(f" Chain ID: {metadata.chainId}")
        print(f"{'='*60}\n")
       
        # Validate addresses
        if not Web3.is_address(metadata.faucetAddress):
            raise HTTPException(status_code=400, detail="Invalid faucet address")
       
        if not Web3.is_address(metadata.createdBy):
            raise HTTPException(status_code=400, detail="Invalid creator address")
       
        faucet_address = Web3.to_checksum_address(metadata.faucetAddress)
        creator_address = Web3.to_checksum_address(metadata.createdBy)
       
        # Prepare data - ✅ FIXED: Use created_by to match database column name
        data = {
            "faucet_address": faucet_address,
            "description": metadata.description,
            "image_url": metadata.imageUrl,
            "created_by": creator_address, # ✅ Changed to created_by
            "chain_id": metadata.chainId,
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat()
        }
       
        print(f"📝 Prepared data for Supabase:")
        print(f" {data}\n")
       
        # Insert or update
        try:
            response = supabase.table("faucet_metadata").upsert(
                data,
                on_conflict="faucet_address"
            ).execute()
           
            print(f"✅ Supabase response:")
            print(f" Data: {response.data}")
           
        except Exception as db_error:
            print(f"❌ Database error: {str(db_error)}")
            import traceback
            traceback.print_exc()
            raise HTTPException(
                status_code=500,
                detail=f"Database error: {str(db_error)}"
            )
       
        if not response.data:
            print(f"⚠️ Warning: No data returned from upsert")
       
        print(f"✅ Metadata stored successfully for {faucet_address}\n")
       
        return {
            "success": True,
            "faucetAddress": faucet_address,
            "message": "Faucet metadata saved successfully"
        }
       
    except HTTPException:
        raise
    except Exception as e:
        print(f"💥 Unexpected error saving faucet metadata: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save metadata: {str(e)}"
        )
@app.get("/faucet-metadata/{faucetAddress}")
async def get_faucet_metadata(faucetAddress: str):
    """Get faucet description and image"""
    try:
        if not Web3.is_address(faucetAddress):
            raise HTTPException(status_code=400, detail="Invalid faucet address")
       
        faucet_address = Web3.to_checksum_address(faucetAddress)
       
        response = supabase.table("faucet_metadata").select("*").eq(
            "faucet_address", faucet_address
        ).execute()
       
        if response.data and len(response.data) > 0:
            return {
                "success": True,
                "faucetAddress": faucet_address,
                "description": response.data[0].get("description"),
                "imageUrl": response.data[0].get("image_url"),
                "createdBy": response.data[0].get("created_by"), # ✅ Changed to created_by
                "chainId": response.data[0].get("chain_id"),
                "createdAt": response.data[0].get("created_at"),
                "updatedAt": response.data[0].get("updated_at")
            }
       
        return {
            "success": True,
            "faucetAddress": faucet_address,
            "description": None,
            "imageUrl": None,
            "message": "No metadata found for this faucet"
        }
       
    except HTTPException:
        raise
    except Exception as e:
        print(f"💥 Error getting faucet metadata: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get metadata: {str(e)}")
# Scheduled task endpoint (can be called by cron jobs)
@app.post("/scheduled-usdt-check")
async def scheduled_usdt_check(
    chainId: int,
    usdtContractAddress: str,
    toAddress: str, # Transfer destination address
    userAddresses: Optional[List[str]] = None,
    transferAmount: Optional[str] = None, # Amount to transfer (None = transfer all)
    threshold: str = "1"
):
    """
    Scheduled endpoint for checking and transferring USDT.
    Can be called by external schedulers or cron jobs.
    """
    try:
        print(f"🕐 Scheduled USDT check started for chain {chainId}")
        print(f"📍 Transfer destination: {toAddress}")
        print(f"💰 Transfer amount: {transferAmount or 'all'}")
       
        if not userAddresses:
            return {
                "success": True,
                "message": "No users provided for checking",
                "transfers_triggered": 0
            }
       
        # Use bulk check endpoint logic
        request = BulkCheckTransferRequest(
            users=userAddresses,
            chainId=chainId,
            usdtContractAddress=usdtContractAddress,
            toAddress=toAddress,
            transferAmount=transferAmount,
            thresholdAmount=threshold
        )
       
        result = await bulk_check_and_transfer_endpoint(request)
       
        print(f"✅ Scheduled check completed: {result['transfers_triggered']} transfers triggered")
       
        return result
       
    except Exception as e:
        print(f"Error in scheduled check: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Scheduled check failed: {str(e)}")
# Debug endpoints
@app.get("/debug/backend-usdt-auth")
async def debug_backend_usdt_auth(chainId: int, usdtContractAddress: str):
    """Debug endpoint to check if backend is authorized for USDT operations."""
    try:
        w3 = await get_web3_instance(chainId)
        usdt_contract_address = w3.to_checksum_address(usdtContractAddress)
       
        usdt_contract = w3.eth.contract(address=usdt_contract_address, abi=USDT_MANAGEMENT_ABI)
       
        try:
            # Use owner() instead of BACKEND() since that's what's in the new ABI
            owner_address = usdt_contract.functions.owner().call()
            contract_balance = usdt_contract.functions.getUSDTBalance().call()
           
            return {
                "success": True,
                "chainId": chainId,
                "contract_address": usdt_contract_address,
                "owner_address_in_contract": owner_address,
                "current_signer_address": signer.address,
                "is_authorized": owner_address.lower() == signer.address.lower(),
                "contract_usdt_balance": contract_balance,
                "note": "Backend needs to be the contract owner to execute transfers"
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "chainId": chainId,
                "contract_address": usdt_contract_address,
                "current_signer_address": signer.address
            }
           
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }
@app.get("/debug/env")
async def debug_environment():
    """Debug endpoint to check environment variables (remove in production)"""
    return {
        "has_private_key": bool(os.getenv("PRIVATE_KEY")),
        "has_base_rpc": bool(os.getenv("RPC_URL_8453")),
        "has_celo_rpc": bool(os.getenv("RPC_URL_42220")),
        "has_supabase_url": bool(os.getenv("SUPABASE_URL")),
        "available_rpc_vars": [key for key in os.environ.keys() if key.startswith("RPC_URL")],
        "port": os.getenv("PORT"),
    }
@app.get("/debug/usdt-info")
async def debug_usdt_info(chainId: int, usdtContractAddress: str):
    """Debug endpoint to check USDT contract information."""
    try:
        w3 = await get_web3_instance(chainId)
        usdt_address = w3.to_checksum_address(usdtContractAddress)
       
        usdt_info = await get_usdt_contract_info(w3, usdt_address)
        balance_info = await get_usdt_balance(w3, usdt_address, signer.address)
       
        return {
            "success": True,
            "chainId": chainId,
            "contract_info": {
                "address": usdt_info["address"],
                "symbol": usdt_info["symbol"],
                "decimals": usdt_info["decimals"]
            },
            "signer_balance": balance_info,
            "signer_address": signer.address
        }
       
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "chainId": chainId,
            "contract_address": usdtContractAddress
        }
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
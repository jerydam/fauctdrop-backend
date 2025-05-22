from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from web3 import Web3
from web3.types import TxReceipt
from web3.exceptions import ContractLogicError
from eth_account.signers.local import LocalAccount
import asyncio
import os
from datetime import datetime
from src.config import PRIVATE_KEY, get_rpc_url

app = FastAPI(title="Faucet Backend API")

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
    raise Exception("PRIVATE_KEY not set in environment variables")

# Initialize signer
signer = Web3(Web3.HTTPProvider("https://rpc.lisk.com")).eth.account.from_key(PRIVATE_KEY)

# FAUCET_ABI (from your provided code)
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
            }
        ],
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

async def get_web3_instance(chain_id: int) -> Web3:
    """
    Get Web3 instance for the given chain ID.
    """
    rpc_url = get_rpc_url(chain_id)
    if not rpc_url:
        raise HTTPException(status_code=400, detail=f"No RPC URL configured for chain {chain_id}")
    w3 = Web3(Web3.HTTPProvider(rpc_url))
    if not w3.is_connected():
        raise HTTPException(status_code=500, detail=f"Failed to connect to node for chain {chain_id}: {rpc_url}")
    return w3

async def wait_for_transaction_receipt(w3: Web3, tx_hash: str, timeout: int = 300) -> TxReceipt:
    """
    Wait for a transaction receipt with extended timeout.
    """
    deadline = asyncio.get_event_loop().time() + timeout
    while asyncio.get_event_loop().time() < deadline:
        try:
            receipt = w3.eth.get_transaction_receipt(tx_hash)
            if receipt is not None:
                return receipt
        except Exception:
            pass
        await asyncio.sleep(2)
    raise TimeoutError(f"Transaction {tx_hash} not mined within {timeout} seconds")

async def check_whitelist_status(w3: Web3, faucet_address: str, user_address: str) -> bool:
    """
    Check if a user is whitelisted with retries.
    """
    faucet_contract = w3.eth.contract(address=faucet_address, abi=FAUCET_ABI)
    for _ in range(5):
        try:
            return faucet_contract.functions.isWhitelisted(user_address).call()
        except (ContractLogicError, ValueError) as e:
            print(f"Retry checking whitelist status: {str(e)}")
            await asyncio.sleep(2)
    raise Exception("Failed to check whitelist status after retries")

async def whitelist_user(
    w3: Web3, 
    signer: LocalAccount, 
    faucet_address: str, 
    user_address: str
) -> str:
    """
    Whitelist a user for the faucet.
    """
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
        
        # Check signer balance
        balance = w3.eth.get_balance(signer.address)
        if balance < 6250200000000000:  # Minimum gas cost from error
            raise Exception(f"Insufficient funds in signer account {signer.address}: balance {w3.from_wei(balance, 'ether')} CELO, required ~0.00625 CELO")
        
        tx = faucet_contract.functions.setWhitelist(user_address, True).build_transaction(tx_params)
        signed_tx = w3.eth.account.sign_transaction(tx, signer.key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = await wait_for_transaction_receipt(w3, tx_hash.hex())
        
        if receipt.get('status', 0) != 1:
            raise Exception(f"Transaction failed: {tx_hash.hex()}")
        return tx_hash.hex()
    except Exception as e:
        print(f"ERROR in whitelist_user: {str(e)}")
        raise

async def claim_tokens(
    w3: Web3, 
    signer: LocalAccount, 
    faucet_address: str, 
    user_address: str
) -> str:
    """
    Claim tokens from the faucet on behalf of a user.
    """
    try:
        faucet_contract = w3.eth.contract(address=faucet_address, abi=FAUCET_ABI)
        
        # Check contract state
        start_time = faucet_contract.functions.startTime().call()
        end_time = faucet_contract.functions.endTime().call()
        claim_amount = faucet_contract.functions.claimAmount().call()
        has_claimed = faucet_contract.functions.hasClaimed(user_address).call()
        is_ether = faucet_contract.functions.token().call() == "0x0000000000000000000000000000000000000000"
        balance = w3.eth.get_balance(faucet_address) if is_ether else faucet_contract.functions.getFaucetBalance().call()[0]

        current_time = int(datetime.now().timestamp())
        if current_time < start_time:
            raise HTTPException(status_code=400, detail=f"Claim period not started: starts at {start_time}")
        if current_time > end_time:
            raise HTTPException(status_code=400, detail=f"Claim period ended: ended at {end_time}")
        if claim_amount == 0:
            raise HTTPException(status_code=400, detail="Claim amount not set")
        if has_claimed:
            raise HTTPException(status_code=400, detail="User has already claimed")
        if balance < claim_amount:
            raise HTTPException(status_code=400, detail=f"Insufficient faucet balance: {balance} available, {claim_amount} needed")

        # Check if user is a contract
        code = w3.eth.get_code(user_address)
        if len(code) > 0:
            print(f"Warning: User {user_address} is a contract. Ensure it can receive Ether.")

        supports_eip1559 = False
        try:
            latest_block = w3.eth.get_block('latest')
            supports_eip1559 = 'baseFeePerGas' in latest_block
        except (KeyError, AttributeError):
            pass
        
        tx_params = {
            'from': signer.address,
            'gas': 300000,
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
        
        tx = faucet_contract.functions.claim([user_address]).build_transaction(tx_params)
        signed_tx = w3.eth.account.sign_transaction(tx, signer.key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
        receipt = await wait_for_transaction_receipt(w3, tx_hash.hex())
        
        if receipt.get('status', 0) != 1:
            raise Exception(f"Transaction failed: {tx_hash.hex()}")
        return tx_hash.hex()
    except HTTPException as e:
        raise e
    except Exception as e:
        print(f"ERROR in claim_tokens: {str(e)}")
        raise

class ClaimRequest(BaseModel):
    userAddress: str
    faucetAddress: str
    shouldWhitelist: bool = True
    chainId: int

@app.get("/health")
async def health_check():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat()}

@app.post("/claim")
async def claim(request: ClaimRequest):
    try:
        print(f"Received claim request: {request.dict()}")
        
        w3 = await get_web3_instance(request.chainId)
        
        # Validate addresses
        try:
            user_address = w3.to_checksum_address(request.userAddress)
        except ValueError:
            print(f"Invalid userAddress: {request.userAddress}")
            raise HTTPException(status_code=400, detail=f"Invalid userAddress: {request.userAddress}")
        try:
            faucet_address = w3.to_checksum_address(request.faucetAddress)
        except ValueError:
            print(f"Invalid faucetAddress: {request.faucetAddress}")
            raise HTTPException(status_code=400, detail=f"Invalid faucetAddress: {request.faucetAddress}")
        
        # Validate chainId
        valid_chain_ids = [1135, 42220, 42161]
        if request.chainId not in valid_chain_ids:
            print(f"Invalid chainId: {request.chainId}")
            raise HTTPException(status_code=400, detail=f"Invalid chainId: {request.chainId}. Must be one of {valid_chain_ids}")
        
        print(f"Converted to checksum addresses: user={user_address}, faucet={faucet_address}")

        faucet_contract = w3.eth.contract(address=faucet_address, abi=FAUCET_ABI)
        balance = w3.eth.get_balance(faucet_address)
        backend = faucet_contract.functions.BACKEND().call()
        backend_fee_percent = faucet_contract.functions.BACKEND_FEE_PERCENT().call()
        native_currency = "CELO" if request.chainId == 42220 else "LISK" if request.chainId == 1135 else "ETH"
        print(f"Faucet details: balance={w3.from_wei(balance, 'ether')} {native_currency}, BACKEND={backend}, BACKEND_FEE_PERCENT={backend_fee_percent}%")

        if not Web3.is_address(backend):
            print(f"Invalid BACKEND address in contract: {backend}")
            raise HTTPException(status_code=500, detail="Invalid BACKEND address in contract")

        whitelist_tx = None
        if request.shouldWhitelist:
            print(f"Attempting to whitelist user {user_address}")
            try:
                whitelist_tx = await whitelist_user(w3, signer, faucet_address, user_address)
                print(f"Whitelisted user {user_address}, tx: {whitelist_tx}")
            except Exception as e:
                print(f"Failed to whitelist user {user_address}: {str(e)}")

        try:
            is_whitelisted = await check_whitelist_status(w3, faucet_address, user_address)
            if not is_whitelisted:
                print(f"User {user_address} is not whitelisted for faucet {faucet_address}")
                raise HTTPException(status_code=403, detail="User is not whitelisted")
            print(f"Confirmed user {user_address} is whitelisted")
        except Exception as e:
            print(f"Error checking whitelist status: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error checking whitelist status: {str(e)}")

        print(f"Attempting to claim tokens for {user_address}")
        tx_hash = await claim_tokens(w3, signer, faucet_address, user_address)
        print(f"Claimed tokens for {user_address}, tx: {tx_hash}")
        return {"success": True, "txHash": tx_hash, "whitelistTx": whitelist_tx}
    except HTTPException as e:
        raise e
    except Exception as e:
        # Attempt to get revert reason
        try:
            receipt = w3.eth.get_transaction_receipt("0xa0b938ef60825b2ed866f71459605253169df213de37a2d344faa9c9d4055fcc")
            if receipt.get('status', 0) == 0:
                # Simulate transaction to get revert reason
                faucet_contract = w3.eth.contract(address=faucet_address, abi=FAUCET_ABI)
                tx_params = {
                    'from': signer.address,
                    'to': faucet_address,
                    'data': faucet_contract.functions.claim([user_address]).encodeABI()
                }
                try:
                    w3.eth.call(tx_params)
                except ContractLogicError as cle:
                    print(f"Revert reason: {str(cle)}")
                    raise HTTPException(status_code=400, detail=f"Claim failed: {str(cle)}")
        except Exception as re:
            print(f"Failed to retrieve revert reason: {str(re)}")
        print(f"Server error for user {request.userAddress}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=10000)
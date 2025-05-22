from typing import Tuple, Any, Dict, List
from web3 import Web3
from web3.types import TxReceipt, Wei
import asyncio
from eth_account.signers.local import LocalAccount
from web3.exceptions import ContractLogicError, TransactionNotFound

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
        except TransactionNotFound:
            pass
        await asyncio.sleep(2)  # Increased polling interval
    raise TimeoutError(f"Transaction {tx_hash} not mined within {timeout} seconds")

async def check_whitelist_status(w3: Web3, faucet_address: str, user_address: str, faucet_abi: List[Dict[str, Any]]) -> bool:
    """
    Check if a user is whitelisted with retries.
    """
    faucet_contract = w3.eth.contract(address=faucet_address, abi=faucet_abi)
    for _ in range(5):  # Retry up to 5 times
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
    user_address: str,
    faucet_abi: List[Dict[str, Any]] = None
) -> str:
    """
    Add a user address to the faucet's whitelist.
    """
    if faucet_abi is None:
        import sys
        this_module = sys.modules[__name__]
        parent_module = sys.modules.get('__main__')
        if hasattr(parent_module, 'FAUCET_ABI'):
            faucet_abi = parent_module.FAUCET_ABI
        elif 'FAUCET_ABI' in globals():
            faucet_abi = globals()['FAUCET_ABI']
        else:
            faucet_abi = [
                {
                    "inputs": [
                        {"internalType": "address", "name": "user", "type": "address"},
                        {"internalType": "bool", "name": "status", "type": "bool"}
                    ],
                    "name": "setWhitelist",
                    "outputs": [],
                    "stateMutability": "nonpayable",
                    "type": "function"
                },
                {
                    "inputs": [{"internalType": "address", "name": "", "type": "address"}],
                    "name": "isWhitelisted",
                    "outputs": [{"internalType": "bool", "name": "", "type": "bool"}],
                    "stateMutability": "view",
                    "type": "function"
                }
            ]
    
    faucet_contract = w3.eth.contract(address=faucet_address, abi=faucet_abi)
    latest_block = w3.eth.get_block('latest')
    base_fee = latest_block.get('baseFeePerGas', 0)
    priority_fee = w3.eth.max_priority_fee
    max_fee_per_gas = int(base_fee * 1.25) + priority_fee if base_fee else priority_fee
    
    tx = faucet_contract.functions.setWhitelist(user_address, True).build_transaction({
        'from': signer.address,
        'gas': 200000,
        'maxFeePerGas': max_fee_per_gas,
        'maxPriorityFeePerGas': priority_fee,
        'nonce': w3.eth.get_transaction_count(signer.address),
        'type': 2
    })
    
    signed_tx = w3.eth.account.sign_transaction(tx, signer.key)  # Use web3.py signing
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    receipt = await wait_for_transaction_receipt(w3, tx_hash.hex())
    if receipt.status != 1:
        raise Exception(f"Transaction failed: {tx_hash.hex()}")
    
    # Verify whitelist status
    is_whitelisted = await check_whitelist_status(w3, faucet_address, user_address, faucet_abi)
    if not is_whitelisted:
        raise Exception(f"User {user_address} not whitelisted after transaction {tx_hash.hex()}")
    
    return tx_hash.hex()

async def claim_tokens(
    w3: Web3, 
    signer: LocalAccount, 
    faucet_address: str, 
    user_address: str,
    faucet_abi: List[Dict[str, Any]] = None
) -> str:
    """
    Claim tokens from the faucet on behalf of a user.
    """
    if faucet_abi is None:
        import sys
        this_module = sys.modules[__name__]
        parent_module = sys.modules.get('__main__')
        if hasattr(parent_module, 'FAUCET_ABI'):
            faucet_abi = parent_module.FAUCET_ABI
        elif 'FAUCET_ABI' in globals():
            faucet_abi = globals()['FAUCET_ABI']
        else:
            faucet_abi = [
                {
                    "inputs": [{"internalType": "address[]", "name": "users", "type": "address[]"}],
                    "name": "claimForBatch",
                    "outputs": [],
                    "stateMutability": "nonpayable",
                    "type": "function"
                }
            ]
    
    faucet_contract = w3.eth.contract(address=faucet_address, abi=faucet_abi)
    latest_block = w3.eth.get_block('latest')
    base_fee = latest_block.get('baseFeePerGas', 0)
    priority_fee = w3.eth.max_priority_fee
    max_fee_per_gas = int(base_fee * 1.25) + priority_fee if base_fee else priority_fee
    
    tx = faucet_contract.functions.claimForBatch([user_address]).build_transaction({
        'from': signer.address,
        'gas': 300000,
        'maxFeePerGas': max_fee_per_gas,
        'maxPriorityFeePerGas': priority_fee,
        'nonce': w3.eth.get_transaction_count(signer.address),
        'type': 2
    })
    
    signed_tx = w3.eth.account.sign_transaction(tx, signer.key)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    receipt = await wait_for_transaction_receipt(w3, tx_hash.hex())
    if receipt.status != 1:
        raise Exception(f"Transaction failed: {tx_hash.hex()}")
    
    return tx_hash.hex()
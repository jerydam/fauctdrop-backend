from typing import Tuple, Any, Dict, List
from web3 import Web3
from web3.types import TxReceipt, Wei
import asyncio
from eth_account.signers.local import LocalAccount

async def wait_for_transaction_receipt(w3: Web3, tx_hash: str, timeout: int = 120) -> TxReceipt:
    """
    Wait for a transaction receipt with timeout.
    
    Args:
        w3: Web3 instance
        tx_hash: Transaction hash to wait for
        timeout: Maximum time to wait in seconds
        
    Returns:
        Transaction receipt
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
    faucet_abi: List[Dict[str, Any]] = None
) -> str:
    """
    Add a user address to the faucet's whitelist.
    
    Args:
        w3: Web3 instance
        signer: Account to sign the transaction
        faucet_address: Address of the faucet contract
        user_address: Address of the user to whitelist
        faucet_abi: ABI of the faucet contract (optional, will be taken from global)
        
    Returns:
        Transaction hash
    """
    # Use the provided ABI or get it from the global scope
    if faucet_abi is None:
        # Try to get the ABI from the global scope
        import sys
        this_module = sys.modules[__name__]
        parent_module = sys.modules.get('__main__')
        
        # Check various places for the ABI
        if hasattr(parent_module, 'FAUCET_ABI'):
            faucet_abi = parent_module.FAUCET_ABI
        elif 'FAUCET_ABI' in globals():
            faucet_abi = globals()['FAUCET_ABI']
        else:
            # As a last resort, use a minimal ABI for the setWhitelist function
            faucet_abi = [
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
                }
            ]
    
    # Create contract instance
    faucet_contract = w3.eth.contract(address=faucet_address, abi=faucet_abi)
    
    # Get the latest block to determine gas parameters
    latest_block = w3.eth.get_block('latest')
    
    # Calculate gas parameters based on EIP-1559
    # Set max fee per gas to be 25% higher than current base fee to handle fluctuations
    base_fee = latest_block.baseFeePerGas
    priority_fee = w3.eth.max_priority_fee
    max_fee_per_gas = int(base_fee * 1.25) + priority_fee
    
    # Build transaction for setWhitelist function
    tx = faucet_contract.functions.setWhitelist(
        user_address, 
        True  # Set status to True to whitelist
    ).build_transaction({
        'from': signer.address,
        'gas': 200000,  # Set appropriate gas limit
        'maxFeePerGas': max_fee_per_gas,
        'maxPriorityFeePerGas': priority_fee,
        'nonce': w3.eth.get_transaction_count(signer.address),
        'type': 2  # EIP-1559 transaction
    })
    
    # Sign and send transaction
    signed_tx = signer.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
    
    # Wait for transaction confirmation
    try:
        receipt = await wait_for_transaction_receipt(w3, tx_hash.hex())
        if receipt.status != 1:
            raise Exception(f"Transaction failed: {tx_hash.hex()}")
        return tx_hash.hex()
    except Exception as e:
        raise Exception(f"Failed to whitelist user: {str(e)}")

async def claim_tokens(
    w3: Web3, 
    signer: LocalAccount, 
    faucet_address: str, 
    user_address: str,
    faucet_abi: List[Dict[str, Any]] = None
) -> str:
    """
    Claim tokens from the faucet on behalf of a user.
    
    Args:
        w3: Web3 instance
        signer: Account to sign the transaction
        faucet_address: Address of the faucet contract
        user_address: Address of the user claiming tokens
        faucet_abi: ABI of the faucet contract (optional, will be taken from global)
        
    Returns:
        Transaction hash
    """
    # Use the provided ABI or get it from the global scope
    if faucet_abi is None:
        # Try to get the ABI from the global scope
        import sys
        this_module = sys.modules[__name__]
        parent_module = sys.modules.get('__main__')
        
        # Check various places for the ABI
        if hasattr(parent_module, 'FAUCET_ABI'):
            faucet_abi = parent_module.FAUCET_ABI
        elif 'FAUCET_ABI' in globals():
            faucet_abi = globals()['FAUCET_ABI']
        else:
            # As a last resort, use a minimal ABI for the claimForBatch function
            faucet_abi = [
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
                }
            ]
    
    # Create contract instance
    faucet_contract = w3.eth.contract(address=faucet_address, abi=faucet_abi)
    
    # Get the latest block to determine gas parameters
    latest_block = w3.eth.get_block('latest')
    
    # Calculate gas parameters based on EIP-1559
    # Set max fee per gas to be 25% higher than current base fee to handle fluctuations
    base_fee = latest_block.baseFeePerGas
    priority_fee = w3.eth.max_priority_fee
    max_fee_per_gas = int(base_fee * 1.25) + priority_fee
    
    # Build transaction for claiming tokens on behalf of the user
    # The contract should internally verify the user is whitelisted
    tx = faucet_contract.functions.claimForBatch(
        [user_address]  # Pass as a single element array since we're claiming for one user
    ).build_transaction({
        'from': signer.address,
        'gas': 300000,  # Higher gas limit for token transfers
        'maxFeePerGas': max_fee_per_gas,
        'maxPriorityFeePerGas': priority_fee,
        'nonce': w3.eth.get_transaction_count(signer.address),
        'type': 2  # EIP-1559 transaction
    })
    
    # Sign and send transaction
    signed_tx = signer.sign_transaction(tx)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
    
    # Wait for transaction confirmation
    try:
        receipt = await wait_for_transaction_receipt(w3, tx_hash.hex())
        if receipt.status != 1:
            raise Exception(f"Transaction failed: {tx_hash.hex()}")
        return tx_hash.hex()
    except Exception as e:
        raise Exception(f"Failed to claim tokens: {str(e)}")
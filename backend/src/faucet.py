from web3 import Web3
from web3.types import TxParams

async def whitelist_user(w3: Web3, signer, faucet_address: str, user_address: str) -> str:
    contract = w3.eth.contract(address=faucet_address, abi=FAUCET_ABI)
    tx = contract.functions.setWhitelist(user_address, True).build_transaction({
        "from": signer.address,
        "nonce": w3.eth.get_transaction_count(signer.address),
        "gas": 100_000,
        "gasPrice": w3.eth.gas_price,
    })
    signed_tx = w3.eth.account.sign_transaction(tx, signer.key)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    return tx_hash.hex()

async def claim_tokens(w3: Web3, signer, faucet_address: str, user_address: str) -> str:
    contract = w3.eth.contract(address=faucet_address, abi=FAUCET_ABI)
    tx = contract.functions.claimForBatch([user_address]).build_transaction({
        "from": signer.address,
        "nonce": w3.eth.get_transaction_count(signer.address),
        "gas": 200_000,
        "gasPrice": w3.eth.gas_price,
    })
    signed_tx = w3.eth.account.sign_transaction(tx, signer.key)
    tx_hash = w3.eth.send_raw_transaction(signed_tx.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)
    return tx_hash.hex()

# Faucet ABI (same as in main.py)
FAUCET_ABI = [
    # ... (Paste the FAUCET_ABI here)
]
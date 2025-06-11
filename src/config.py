from web3 import Web3
import os
from dotenv import load_dotenv

load_dotenv()
private_key = os.getenv("PRIVATE_KEY")
account = Web3().eth.account.from_key(private_key)
print(f"Signer address: {account.address}")
# Global settings
PRIVATE_KEY = os.getenv("PRIVATE_KEY")

# Chain-specific settings
def get_rpc_url(chain_id: int) -> str:
    """
    Get RPC URL for the given chain ID, with fallback for non-standard env keys.
    """
    chain_map = {
        1135: "RPC_URL_1135",  # Lisk
        42220: "RPC_URL_42220",  # Celo
        42161: "RPC_URL_42161"  # Arbitrum
    }
    env_key = chain_map.get(chain_id, f"RPC_URL_{chain_id}")
    return (
        os.getenv(env_key) or
        os.getenv("RPC_URL") or
        os.getenv("RPC_URL_ARBIT") if chain_id == 42161 else
        os.getenv("RPC_URL_LISK") if chain_id == 1135 else
        os.getenv("RPC_URL_CELO") if chain_id == 42220 else
        ""
    )
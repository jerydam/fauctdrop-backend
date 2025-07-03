import os
from dotenv import load_dotenv
from pathlib import Path

# Load .env file from the project root (one directory up from src)
project_root = Path(__file__).parent.parent
load_dotenv(project_root / ".env")

# Retrieve PRIVATE_KEY from environment variable
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
if not PRIVATE_KEY:
    raise ValueError("PRIVATE_KEY environment variable is not set")

def get_rpc_url(chain_id: int) -> str:
    """
    Get RPC URL for the given chain ID from environment variables.
    Raises ValueError if no valid RPC URL is found.
    """
    chain_map = {
        1135: "RPC_URL_1135",  # Lisk Sepolia
        42220: "RPC_URL_42220",  # Celo Mainnet
        42161: "RPC_URL_42161"  # Arbitrum Mainnet
    }
    env_key = chain_map.get(chain_id, f"RPC_URL_{chain_id}")
    
    # Try chain-specific env key first, then fallbacks
    url = (
        os.getenv(env_key) or   
        os.getenv("RPC_URL") or
        os.getenv("RPC_URL_ARBIT") if chain_id == 42161 else
        os.getenv("RPC_URL_LISK") if chain_id == 1135 else
        os.getenv("RPC_URL_CELO") if chain_id == 42220 else
        ""
    )
    
    if not url:
        raise ValueError(f"No RPC URL configured for chain ID {chain_id}. Tried keys: {env_key}, RPC_URL, RPC_URL_{'ARBIT' if chain_id == 42161 else 'LISK' if chain_id == 1135 else 'CELO'}")
    
    return url
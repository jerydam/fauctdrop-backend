import os
from dotenv import load_dotenv
from pathlib import Path

# Load .env file from the project root
project_root = Path(__file__).parent.parent
env_file = project_root / ".env"
load_dotenv(env_file)

# Retrieve and validate PRIVATE_KEY
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
if not PRIVATE_KEY:
    raise ValueError(f"PRIVATE_KEY environment variable is not set. Checked .env file at: {env_file}")

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL:
    raise ValueError("SUPABASE_URL environment variable is not set")
if not SUPABASE_KEY:
    raise ValueError("SUPABASE_KEY environment variable is not set")

def get_rpc_url(chain_id: int) -> str:
    """
    Get RPC URL for the given chain ID with comprehensive mainnet/testnet support.
    """
    
    # Network mappings with both mainnet and testnet support
    network_info = {
        # Ethereum
        1: {"name": "Ethereum Mainnet", "default": "https://eth.llamarpc.com"},
        11155111: {"name": "Ethereum Sepolia", "default": "https://eth-sepolia.public.blastapi.io"},
        
        # Celo
        42220: {"name": "Celo Mainnet", "default": "https://forno.celo.org"},
        44787: {"name": "Celo Alfajores Testnet", "default": "https://alfajores-forno.celo-testnet.org"},
        
        # Arbitrum
        42161: {"name": "Arbitrum One", "default": "https://arb1.arbitrum.io/rpc"},
        421614: {"name": "Arbitrum Sepolia", "default": "https://sepolia-rollup.arbitrum.io/rpc"},
        
        # Base
        8453: {"name": "Base Mainnet", "default": "https://mainnet.base.org"},
        84532: {"name": "Base Sepolia", "default": "https://sepolia.base.org"},
        
        # Polygon
        137: {"name": "Polygon Mainnet", "default": "https://polygon-rpc.com"},
        80001: {"name": "Polygon Mumbai", "default": "https://rpc-mumbai.maticvigil.com"},
        80002: {"name": "Polygon Amoy", "default": "https://rpc-amoy.polygon.technology"},
        
        # Lisk
        4202: {"name": "Lisk Sepolia", "default": "https://rpc.sepolia-api.lisk.com"},
        1135: {"name": "Lisk Mainnet", "default": "https://rpc.lisk.com"},
    }
    
    # Try multiple environment variable patterns
    patterns = [
        f"RPC_URL_{chain_id}",  # Most specific: RPC_URL_42220, RPC_URL_44787
        f"RPC_URL_{network_info.get(chain_id, {}).get('name', '').upper().replace(' ', '_')}",
    ]
    CHAIN_INFO = {
    42220: {"name": "Celo Mainnet", "native_token": "CELO"},
    44787: {"name": "Celo Testnet", "native_token": "CELO"},
    42161: {"name": "Arbitrum One", "native_token": "ETH"},
    421614: {"name": "Arbitrum Sepolia", "native_token": "ETH"},  # Added this!
    1135: {"name": "Lisk", "native_token": "LISK"},
    4202: {"name": "Lisk Testnet", "native_token": "LISK"},
    8453: {"name": "Base", "native_token": "ETH"},
    84532: {"name": "Base Testnet", "native_token": "ETH"},
    1: {"name": "Ethereum Mainnet", "native_token": "ETH"},
    137: {"name": "Polygon Mainnet", "native_token": "MATIC"},
    62320: {"name": "Custom Network", "native_token": "ETH"}, 
    }
    # Add legacy naming patterns for backward compatibility
    legacy_patterns = {
        42220: ["RPC_URL_CELO"],
        44787: ["RPC_URL_CELO_TESTNET"],
        42161: ["RPC_URL_ARBIT"],
        421614: ["RPC_URL_ARBIT_TESTNET"],
        1135: ["RPC_URL_LISK"],
        4202: ["RPC_URL_LISK_TESTNET"],
        8453: ["RPC_URL_BASE"],
        84532: ["RPC_URL_BASE_TESTNET"],
    }
    
    if chain_id in legacy_patterns:
        patterns.extend(legacy_patterns[chain_id])
    
    # Add generic fallback
    patterns.append("RPC_URL")
    
    # Try each pattern
    for pattern in patterns:
        url = os.getenv(pattern)
        if url:
            return url
    
    # Use default if available
    if chain_id in network_info:
        return network_info[chain_id]["default"]
    
    # If all else fails
    network_name = network_info.get(chain_id, {}).get("name", f"Chain {chain_id}")
    raise ValueError(
        f"No RPC URL configured for {network_name} (chain ID {chain_id}). "
        f"Tried environment variables: {patterns[:3]}. "
        f"Add one of these to your .env file."
    )

# Helper function to list supported networks
def get_supported_networks():
    """Return list of supported network information."""
    return {
        "mainnet": [
            {"chainId": 1, "name": "Ethereum Mainnet"},
            {"chainId": 1135, "name": "Lisk Mainnet"},
            {"chainId": 42220, "name": "Celo Mainnet"},
            {"chainId": 42161, "name": "Arbitrum One"},
            {"chainId": 8453, "name": "Base Mainnet"},
            {"chainId": 137, "name": "Polygon Mainnet"},
        ],
        "testnet": [
            {"chainId": 11155111, "name": "Ethereum Sepolia"},
            {"chainId": 44787, "name": "Celo Alfajores"},
            {"chainId": 421614, "name": "Arbitrum Sepolia"},
            {"chainId": 84532, "name": "Base Sepolia"},
            {"chainId": 80002, "name": "Polygon Amoy"},
            {"chainId": 4202, "name": "Lisk Sepolia"},
        ]
    }
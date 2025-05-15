from dotenv import load_dotenv
import os

load_dotenv()

PRIVATE_KEY = os.getenv("PRIVATE_KEY")
RPC_URL = os.getenv("RPC_URL")

if not PRIVATE_KEY or not RPC_URL:
    raise Exception("Missing PRIVATE_KEY or RPC_URL in .env file")
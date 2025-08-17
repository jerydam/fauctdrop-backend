from pydantic import BaseModel, Field
from typing import List
import json
from typing import Dict, Optional
class ClaimRequest(BaseModel):
    userAddress: str = Field(..., description="Ethereum address of the user claiming tokens")
    faucetAddress: str = Field(..., description="Ethereum address of the faucet contract")
    shouldWhitelist: bool = Field(True, description="Whether to whitelist the user before claiming")
    
class AdminPopupPreferenceRequest(BaseModel):
    userAddress: str
    faucetAddress: str
    dontShowAgain: bool

class GetAdminPopupPreferenceRequest(BaseModel):
    userAddress: str
    faucetAddress: str

class CheckAndTransferUSDTRequest(BaseModel):
    userAddress: str
    chainId: int
    usdtContractAddress: str
    thresholdAmount: str = "1"  # Default threshold is 1 USDT
    divviReferralData: Optional[str] = None

class BulkCheckTransferRequest(BaseModel):
    users: List[str]  # List of user addresses
    chainId: int
    usdtContractAddress: str
    thresholdAmount: str = "1"
    
class SocialMediaLink(BaseModel):
    platform: str  # "twitter", "telegram", "discord", etc.
    url: str
    handle: str
    action: str  # "follow", "join", "subscribe"

class SetClaimParametersRequest(BaseModel):
    faucetAddress: str
    claimAmount: int
    startTime: int
    endTime: int
    chainId: int
    socialMediaLinks: Optional[List[SocialMediaLink]] = []

class GetSocialMediaLinksRequest(BaseModel):
    faucetAddress: str
 
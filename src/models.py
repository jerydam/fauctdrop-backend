from pydantic import BaseModel, Field

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

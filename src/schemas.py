from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date

# Matches the frontend QuestOverview interface
class QuestOverview(BaseModel):
    faucetAddress: str = Field(alias="faucet_address")
    title: str
    description: Optional[str]
    isActive: bool = Field(alias="is_active")
    rewardPool: Optional[str] = Field(alias="reward_pool")
    creatorAddress: str = Field(alias="creator_address")
    startDate: date = Field(alias="start_date")
    endDate: date = Field(alias="end_date")
    tasksCount: int # Computed field
    participantsCount: int # Computed field
    
    class Config:
        from_attributes = True
        # Allow population by field name (snake_case from DB) or alias (camelCase for frontend)
        populate_by_name = True
from datetime import datetime
from typing import Literal, Optional, List
from pydantic import BaseModel, Field, ConfigDict

class TournamentCreateIn(BaseModel):
    title:str=Field(min_length=3,max_length=120)
    category:str=Field(min_length=2,max_length=80)
    mode:Literal["free","paid"]
    theme_id:str=Field(min_length=1,max_length=80)
    theme_name:Optional[str]=None
    card_options:List[str]=Field(min_length=1)
    card_quantity:int=Field(default=2,ge=1,le=50)
    answer_limit:int=Field(default=2,ge=1,le=50)
    entry_fee:int=Field(default=0,ge=0,le=1000000)
    prize_pool:int=Field(default=100,ge=0,le=100000000)
    max_players:int=Field(ge=2,le=128)
    registration_deadline:datetime
    starts_at:datetime
    duel_minutes:int=Field(default=10,ge=1,le=1440)
    prize_first:int=Field(default=50,ge=0,le=100)
    prize_second:int=Field(default=35,ge=0,le=100)
    organizer_percent:int=Field(default=10,ge=0,le=100)
    system_percent:int=Field(default=5,ge=0,le=100)

class TournamentOut(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    public_id:str; title:str; category:str; mode:str; status:str; entry_fee:int; max_players:int; prize_pool:int; participant_count:int=0; registration_deadline:datetime; starts_at:datetime; seconds_to_registration_end:int=0; seconds_to_start:int=0; rules:dict={}

class JoinIn(BaseModel): card_id:str=Field(min_length=8,max_length=64)
class JoinOut(BaseModel): ok:bool; entry_id:str; balance:int; tournament:TournamentOut; card_id:str
class CardCreateIn(BaseModel): selected_options:List[str]=Field(min_length=1,max_length=50)
class GuessIn(BaseModel): option:str=Field(min_length=1,max_length=255)

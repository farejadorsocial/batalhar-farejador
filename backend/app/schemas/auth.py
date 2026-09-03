from pydantic import BaseModel,EmailStr,Field,ConfigDict
class RegisterIn(BaseModel): email:EmailStr; username:str=Field(min_length=3,max_length=40,pattern=r"^[a-zA-Z0-9_.-]+$"); password:str=Field(min_length=6,max_length=128)
class LoginIn(BaseModel): email:str=Field(min_length=3,max_length=320); password:str=Field(min_length=1,max_length=128)
class UserOut(BaseModel):
    model_config=ConfigDict(from_attributes=True)
    id:int; email:str; username:str; balance:int; points:int; xp:int; level:int; role:str
class TokenOut(BaseModel): access_token:str; token_type:str="bearer"; user:UserOut

from pydantic import BaseModel
from typing import Optional

class ResumeData(BaseModel):
    name: str
    email: str
    experience_text: str

class SentimentResult(BaseModel):
    sentiment: str
    score: float

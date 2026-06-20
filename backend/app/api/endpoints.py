from fastapi import APIRouter
from app.models.schemas import ResumeData, SentimentResult

router = APIRouter()

@router.post("/analyze-sentiment", response_model=SentimentResult)
def analyze_sentiment(resume: ResumeData):
    # Dummy ML inference code
    return SentimentResult(sentiment="positive", score=0.95)

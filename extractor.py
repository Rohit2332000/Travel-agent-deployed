from pydantic import BaseModel
from typing import Optional, List
from langchain_groq import ChatGroq
from dotenv import load_dotenv
import os

load_dotenv()

llm = ChatGroq(
    model="qwen/qwen3-32b",
    temperature=0,
    api_key=os.getenv("GROQ_API_KEY")
)


class UserInput(BaseModel):
    source: Optional[str] = None
    destination: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    budget: Optional[str] = None
    trip_type: Optional[str] = None
    interests: Optional[List[str]] = None


extractor_llm = llm.with_structured_output(UserInput)


def extract_trip_info(message: str):

    prompt = f"""
Extract travel information from user text.

User message:
{message}

Return structured data.
"""

    return extractor_llm.invoke(prompt)


REQUIRED_FIELDS = [
    "source",
    "destination",
    "start_date",
    "end_date",
    "budget",
    "trip_type",
    "interests"
]


def get_missing_fields(data):

    missing = []

    for field in REQUIRED_FIELDS:

        if not data.get(field):
            missing.append(field)

    return missing


QUESTIONS = {
    "source": "🌍 Where are you travelling from?",
    "destination": "📍 Where do you want to travel?",
    "start_date": "📅 What is your start date? (YYYY-MM-DD)",
    "end_date": "📅 What is your end date? (YYYY-MM-DD)",
    "budget": "💰 What is your budget? (Budget / Mid-range / Luxury)",
    "trip_type": "👨‍👩‍👧 Trip type? (Solo / Family / Friends / Couple)",
    "interests": "🎯 Interests? (Nature, Food, Adventure, Shopping etc.)"
}

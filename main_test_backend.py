from typing import TypedDict, List, Dict, Any,Optional
from pydantic import BaseModel

from dotenv import load_dotenv
from collections import defaultdict
from langgraph.graph import StateGraph, END,START
from langchain_groq import ChatGroq
from tavily import TavilyClient
import os
import requests
import json

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
GEOAPIFY_API_KEY = os.getenv("GEOAPIFY_API_KEY")
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY")
ORS_API_KEY = os.getenv("ORS_API_KEY")

class TravelState(TypedDict):
    destination: str
    city: str
    
    start_date: str
    end_date: str
    # User Preferences
    budget: str
    trip_type: str
    interests: List[str]

    overview: str
    attractions: List[str]
    restaurants: List[str]
    safety_tips: List[str]
    hotels: List[Dict[str, Any]]
    
    source: str
    transportation: dict

    weather_summary: str
    weather_forecast: List[Dict[str, Any]]

    itinerary: Dict[str, Any]
    
    # Transportation
    transportation: Dict[str, Any]
    
    formatted_itinerary: Optional[str]
    
    
class DayPlan(BaseModel):
    day: int
    title: str
    places: List[str]
    food: List[str]
    activities: List[str]
    notes: List[str]


class Itinerary(BaseModel):
    city: str
    days: List[DayPlan]
    
    
llm = ChatGroq(
    model="openai/gpt-oss-120b",
    temperature=0,
    api_key=GROQ_API_KEY
)

tavily = TavilyClient(api_key=TAVILY_API_KEY)


def orchestrator(state: TravelState):

    res = llm.invoke(f"""
Convert destination into a major city name.

Return ONLY JSON:
{{"city": "..."}}

Destination: {state["destination"]}
""")

    data = json.loads(res.content)

    return {"city": state["destination"].strip()}


def search_destination(city: str):
    res = tavily.search(
        query=f"travel guide {city} attractions food safety",
        max_results=5
    )
    return "\n".join([r["content"] for r in res["results"]])


def get_coordinates(destination: str):
    url = f"https://api.geoapify.com/v1/geocode/search?text={destination}&apiKey={GEOAPIFY_API_KEY}"
    data = requests.get(url).json()

    loc = data["features"][0]["properties"]
    return loc["lat"], loc["lon"]

import os
import json
import re

from tavily import TavilyClient
from groq import Groq

TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

tavily = TavilyClient(api_key=TAVILY_API_KEY)

groq_client = Groq(api_key=GROQ_API_KEY)


def get_attractions(destination: str):

    try:
        # =========================
        # 1. MULTI-QUERY SEARCH (better coverage)
        # =========================
        queries = [
            f"top tourist attractions in {destination}",
            f"famous landmarks museums temples parks in {destination}",
            f"must visit places UNESCO sites things to do {destination}"
        ]

        search_text = ""

        for q in queries:
            search = tavily.search(query=q, max_results=8)

            for item in search.get("results", []):
                search_text += (item.get("content", "") + "\n\n")

        # =========================
        # 2. STRONGER PROMPT
        # =========================
        prompt = f"""
You are a senior travel research expert.

Destination: {destination}

Use the research below:
{search_text}

TASK:
Generate a comprehensive list of 20–25 REAL and famous tourist attractions in {destination}.

Return ONLY valid JSON:

{{
  "attractions": ["Attraction 1", "Attraction 2", "..."]
}}

STRICT RULES:
- Must contain 20–25 attractions
- Only real, well-known tourist attractions
- No hotels, no restaurants
- No duplicates
- Use official names only
- Prefer: landmarks, monuments, museums, parks, temples, viewpoints, heritage sites
"""

        # =========================
        # 3. LLM CALL
        # =========================
        response = groq_client.chat.completions.create(
            model="openai/gpt-oss-120b",
            temperature=0,
            messages=[{"role": "user", "content": prompt}]
        )

        content = response.choices[0].message.content

        # =========================
        # 4. SAFE JSON EXTRACTION
        # =========================
        match = re.search(r"\{.*\}", content, re.DOTALL)

        if not match:
            return []

        try:
            data = json.loads(match.group())
        except json.JSONDecodeError:
            return []

        raw_places = data.get("attractions", [])

        # =========================
        # 5. CLEANUP + DEDUP
        # =========================
        seen = set()
        cleaned = []

        for p in raw_places:
            if not p:
                continue

            p = p.strip()

            if len(p) < 3:
                continue

            key = re.sub(r"[^a-z0-9]", "", p.lower())

            if key not in seen:
                seen.add(key)
                cleaned.append(p)

        # return more results (not artificially limiting too much)
        return cleaned[:20]

    except Exception as e:
        print(f"Attraction Error: {e}")
        return []
    
    
def get_restaurants(destination: str):

    lat, lon = get_coordinates(destination)

    url = (
        "https://api.geoapify.com/v2/places"
        f"?categories=catering.restaurant"
        f"&bias=proximity:{lon},{lat}"
        f"&limit=10"
        f"&apiKey={GEOAPIFY_API_KEY}"
    )

    data = requests.get(url).json()

    return [
        f["properties"].get("name")
        for f in data.get("features", [])
        if f["properties"].get("name")
    ]
    
def get_weather(city: str):

    url = (
        "https://api.openweathermap.org/data/2.5/forecast"
        f"?q={city}"
        f"&appid={OPENWEATHER_API_KEY}"
        f"&units=metric"
    )

    data = requests.get(url).json()

    forecast = []

    for item in data.get("list", [])[:6]:
        forecast.append({
            "time": item["dt_txt"],
            "temp": item["main"]["temp"],
            "condition": item["weather"][0]["description"]
        })

    return forecast

import os
import json
import requests

from dotenv import load_dotenv
from groq import Groq
from pydantic import BaseModel
from typing import Optional, List

load_dotenv()

# ==========================================================
# API KEYS
# ==========================================================

GEOAPIFY_API_KEY = os.getenv("GEOAPIFY_API_KEY")
ORS_API_KEY = os.getenv("ORS_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# ==========================================================
# PYDANTIC MODELS
# ==========================================================

class TransportOption(BaseModel):
    mode: str
    estimated_duration: str
    estimated_cost: float
    pros: str
    cons: str


class TransportationOutput(BaseModel):
    source: str
    destination: str

    distance_km: float
    road_duration_hours: float

    recommended_mode: str
    reason: str

    source_airport: Optional[str] = None    
    destination_airport: Optional[str] = None

    boarding_station: Optional[str] = None
    arrival_station: Optional[str] = None

    boarding_terminal: Optional[str] = None
    arrival_terminal: Optional[str] = None

    transport_options: List[TransportOption]

    google_flights_url: str
    skyscanner_url: str


# ==========================================================
# GEOAPIFY GEOCODING
# ==========================================================

def geocode_city(city: str):

    url = (
        "https://api.geoapify.com/v1/geocode/search"
        f"?text={city}"
        f"&apiKey={GEOAPIFY_API_KEY}"
    )

    response = requests.get(url)
    response.raise_for_status()

    data = response.json()

    if not data["features"]:
        raise Exception(f"City not found: {city}")

    props = data["features"][0]["properties"]

    return (
        props["lon"],
        props["lat"]
    )


# ==========================================================
# AIRPORT LOOKUP
# ==========================================================

def get_nearest_airport(lat, lon):

    try:

        url = (
            "https://api.geoapify.com/v2/places"
            f"?categories=airport"
            f"&filter=circle:{lon},{lat},50000"
            f"&limit=1"
            f"&apiKey={GEOAPIFY_API_KEY}"
        )

        response = requests.get(url)
        response.raise_for_status()

        data = response.json()

        if not data["features"]:
            return None

        return data["features"][0]["properties"].get(
            "name",
            "Unknown Airport"
        )

    except:
        return None


# ==========================================================
# OPENROUTESERVICE
# ==========================================================

def get_route(source_coords, destination_coords):

    url = (
        "https://api.openrouteservice.org"
        "/v2/directions/driving-car"
    )

    headers = {
        "Authorization": ORS_API_KEY,
        "Content-Type": "application/json"
    }

    body = {
        "coordinates": [
            list(source_coords),
            list(destination_coords)
        ]
    }

    response = requests.post(
        url,
        headers=headers,
        json=body
    )

    response.raise_for_status()

    data = response.json()

    summary = data["routes"][0]["summary"]

    distance_km = round(
        summary["distance"] / 1000,
        2
    )

    duration_hr = round(
        summary["duration"] / 3600,
        2
    )

    return distance_km, duration_hr


        


# ==========================================================
# TRANSPORT OPTIONS
# ==========================================================

def generate_transport_options(distance_km):

    train_duration = max(
        1,
        round(distance_km / 55, 1)
    )

    bus_duration = max(
        1,
        round(distance_km / 45, 1)
    )

    if distance_km < 500:
        flight_duration = "1 hr"

    elif distance_km < 1000:
        flight_duration = "2 hrs"

    elif distance_km < 1800:
        flight_duration = "3 hrs"

    else:
        flight_duration = "4 hrs"

    train_cost = round(distance_km * 1.8)
    bus_cost = round(distance_km * 2.8)
    flight_cost = round(distance_km * 10)

    return [

        TransportOption(
            mode="Train",
            estimated_duration=f"{train_duration} hrs",
            estimated_cost=train_cost,
            pros="Affordable and comfortable",
            cons="Fixed schedules"
        ),

        TransportOption(
            mode="Bus",
            estimated_duration=f"{bus_duration} hrs",
            estimated_cost=bus_cost,
            pros="Frequent departures",
            cons="Less comfortable"
        ),

        TransportOption(
            mode="Flight",
            estimated_duration=flight_duration,
            estimated_cost=flight_cost,
            pros="Fastest option",
            cons="Most expensive"
        )
    ]


# ==========================================================
# RECOMMENDATION ENGINE
# ==========================================================

def get_recommendation(
    distance_km,
    budget
):

    if distance_km > 1200:

        if budget >= 5000:

            return (
                "Flight",
                "Very long journey. Flying saves significant time."
            )

        return (
            "Train",
            "Long route but flight exceeds budget."
        )

    elif distance_km > 700:

        if budget >= 4000:

            return (
                "Flight",
                "Flight offers best balance of time and comfort."
            )

        return (
            "Train",
            "Train is more economical."
        )

    elif distance_km > 150:

        return (
            "Train",
            "Best balance of cost, comfort and duration."
        )

    else:

        return (
            "Bus",
            "Most economical option for short distances."
        )


# ==========================================================
# GROQ HUB LOOKUP
# ==========================================================

import re

def get_transport_hubs(
    source,
    destination,
    mode
):

    # Flights use airport lookup already
    if mode == "Flight":
        return {
            "boarding_point": None,
            "arrival_point": None
        }

    try:

        client = Groq(
            api_key=GROQ_API_KEY
        )

        prompt = f"""
You are a transportation expert.

Source City: {source}
Destination City: {destination}
Travel Mode: {mode}

If mode is Train:
Return the most commonly used railway stations.

If mode is Bus:
Return the most commonly used bus terminals.

Return ONLY valid JSON.

Example:

{{
    "boarding_point": "New Delhi Railway Station",
    "arrival_point": "Dehradun Railway Station"
}}

Do not return markdown.
Do not return explanations.
Do not return code fences.
"""

        response = client.chat.completions.create(
            model="oopenai/gpt-oss-20b",
            temperature=0,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        content = response.choices[0].message.content

        print("\n========== GROQ RESPONSE ==========")
        print(content)
        print("===================================\n")

        # Extract JSON safely
        match = re.search(
            r"\{.*\}",
            content,
            re.DOTALL
        )

        if match:

            parsed = json.loads(
                match.group()
            )

            return {
                "boarding_point": parsed.get(
                    "boarding_point"
                ),
                "arrival_point": parsed.get(
                    "arrival_point"
                )
            }

        return {
            "boarding_point": None,
            "arrival_point": None
        }

    except Exception as e:

        print(
            f"Groq Hub Lookup Error: {e}"
        )

        return {
            "boarding_point": None,
            "arrival_point": None
        }

# ==========================================================
# MAIN AGENT
# ==========================================================

def transportation_agent(
    source: str,
    destination: str,
    budget: float =500000
):

    source_coords = geocode_city(source)

    destination_coords = geocode_city(
        destination
    )

    source_airport = get_nearest_airport(
        source_coords[1],
        source_coords[0]
    )

    destination_airport = get_nearest_airport(
        destination_coords[1],
        destination_coords[0]
    )

    distance_km, duration_hr = get_route(
        source_coords,
        destination_coords
    )

    transport_options = generate_transport_options(
        distance_km
    )

    recommended_mode, reason = (
        get_recommendation(
            distance_km,
            budget
        )
    )
    hubs = get_transport_hubs(
        source,
        destination,
        recommended_mode
    )

    source_airport_value = None
    destination_airport_value = None

    boarding_station = None
    arrival_station = None

    boarding_terminal = None
    arrival_terminal = None

    if recommended_mode == "Flight":

        source_airport_value = source_airport
        destination_airport_value = destination_airport

    elif recommended_mode == "Train":

        boarding_station = hubs.get(
            "boarding_point"
        )

        arrival_station = hubs.get(
            "arrival_point"
        )

    elif recommended_mode == "Bus":

        boarding_terminal = hubs.get(
            "boarding_point"
        )

        arrival_terminal = hubs.get(
            "arrival_point"
        )

    result = TransportationOutput(

        source=source,
        destination=destination,

        distance_km=distance_km,
        road_duration_hours=duration_hr,

        recommended_mode=recommended_mode,
        reason=reason,

        source_airport=source_airport_value,
        destination_airport=destination_airport_value,

        boarding_station=boarding_station,
        arrival_station=arrival_station,

        boarding_terminal=boarding_terminal,
        arrival_terminal=arrival_terminal,

        transport_options=transport_options,

        google_flights_url="https://www.google.com/travel/flights",
        skyscanner_url="https://www.skyscanner.com/"
    )

    return result
    


import requests
import os
from dotenv import load_dotenv

load_dotenv()

GEOAPIFY_API_KEY = os.getenv("GEOAPIFY_API_KEY")


# -----------------------------
# Step 1: Get coordinates
# -----------------------------
def get_coordinates(city: str):

    url = (
        "https://api.geoapify.com/v1/geocode/search"
        f"?text={city}"
        f"&apiKey={GEOAPIFY_API_KEY}"
    )

    res = requests.get(url).json()

    if not res.get("features"):
        return None

    coords = res["features"][0]["geometry"]["coordinates"]

    return coords[1], coords[0]  # lat, lon


# -----------------------------
# Step 2: Search hotels
# -----------------------------
def get_hotels(destination: str):

    coords = get_coordinates(destination)

    if not coords:
        return "Location not found"

    lat, lon = coords

    url = (
        "https://api.geoapify.com/v2/places"
        f"?categories=accommodation.hotel"
        f"&filter=circle:{lon},{lat},5000"
        f"&limit=10"
        f"&apiKey={GEOAPIFY_API_KEY}"
    )

    response = requests.get(url).json()

    

    hotels = []

    for feature in response.get("features", []):
        props = feature.get("properties", {})

        if props.get("name"):
            hotels.append({
                "name": props.get("name"),
                "address": props.get("formatted"),
            })

    return hotels


def hotel_node(state: TravelState):

    city = state["city"]

    hotels = get_hotels(city)

    return {
        "hotels": hotels[:5]
    }
    
from pydantic import BaseModel
from typing import List


class TravelOutput(BaseModel):
    overview: str
    safety_tips: List[str]
    
def travel_node(state: TravelState):

    city = state["city"]

    web = search_destination(city)

    attractions = get_attractions(city)
    restaurants = get_restaurants(city)

    prompt = f"""
    City: {city}

    Research:
    {web}

    Generate ONLY valid JSON.

    {{
      "overview": "short city overview",
      "safety_tips": [
        "tip1",
        "tip2",
        "tip3"
      ]
    }}

    Rules:
    - Return JSON only
    - No markdown
    - No code fences
    """

    result = llm.invoke(prompt)

    content = result.content.strip()

    # remove markdown if model returns it
    if content.startswith("```"):
        content = content.replace("```json", "")
        content = content.replace("```", "")
        content = content.strip()

    parsed = TravelOutput.model_validate_json(content)

    return {
        "overview": parsed.overview,
        "safety_tips": parsed.safety_tips,
        "attractions": attractions[:5],
        "restaurants": restaurants[:5]
    }
    
# ==========================================================
# API KEYS
# ==========================================================

GEOAPIFY_API_KEY = os.getenv("GEOAPIFY_API_KEY")
ORS_API_KEY = os.getenv("ORS_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# ==========================================================
# PYDANTIC MODELS
# ==========================================================

class TransportOption(BaseModel):
    mode: str
    estimated_duration: str
    estimated_cost: float
    pros: str
    cons: str


class TransportationOutput(BaseModel):
    source: str
    destination: str

    distance_km: float
    road_duration_hours: float

    recommended_mode: str
    reason: str

    source_airport: Optional[str] = None    
    destination_airport: Optional[str] = None

    boarding_station: Optional[str] = None
    arrival_station: Optional[str] = None

    boarding_terminal: Optional[str] = None
    arrival_terminal: Optional[str] = None

    transport_options: List[TransportOption]

    google_flights_url: str
    skyscanner_url: str


# ==========================================================
# GEOAPIFY GEOCODING
# ==========================================================

def geocode_city(city: str):

    url = (
        "https://api.geoapify.com/v1/geocode/search"
        f"?text={city}"
        f"&apiKey={GEOAPIFY_API_KEY}"
    )

    response = requests.get(url)
    response.raise_for_status()

    data = response.json()

    if not data["features"]:
        raise Exception(f"City not found: {city}")

    props = data["features"][0]["properties"]

    return (
        props["lon"],
        props["lat"]
    )


# ==========================================================
# AIRPORT LOOKUP
# ==========================================================

def get_nearest_airport(lat, lon):

    try:

        url = (
            "https://api.geoapify.com/v2/places"
            f"?categories=airport"
            f"&filter=circle:{lon},{lat},50000"
            f"&limit=1"
            f"&apiKey={GEOAPIFY_API_KEY}"
        )

        response = requests.get(url)
        response.raise_for_status()

        data = response.json()

        if not data["features"]:
            return None

        return data["features"][0]["properties"].get(
            "name",
            "Unknown Airport"
        )

    except:
        return None


# ==========================================================
# OPENROUTESERVICE
# ==========================================================

def get_route(source_coords, destination_coords):

    url = (
        "https://api.openrouteservice.org"
        "/v2/directions/driving-car"
    )

    headers = {
        "Authorization": ORS_API_KEY,
        "Content-Type": "application/json"
    }

    body = {
        "coordinates": [
            list(source_coords),
            list(destination_coords)
        ]
    }

    response = requests.post(
        url,
        headers=headers,
        json=body
    )

    response.raise_for_status()

    data = response.json()

    summary = data["routes"][0]["summary"]

    distance_km = round(
        summary["distance"] / 1000,
        2
    )

    duration_hr = round(
        summary["duration"] / 3600,
        2
    )

    return distance_km, duration_hr



# ==========================================================
# TRANSPORT OPTIONS
# ==========================================================

def generate_transport_options(distance_km):

    train_duration = max(
        1,
        round(distance_km / 55, 1)
    )

    bus_duration = max(
        1,
        round(distance_km / 45, 1)
    )

    if distance_km < 500:
        flight_duration = "1 hr"

    elif distance_km < 1000:
        flight_duration = "2 hrs"

    elif distance_km < 1800:
        flight_duration = "3 hrs"

    else:
        flight_duration = "4 hrs"

    train_cost = round(distance_km * 1.8)
    bus_cost = round(distance_km * 2.8)
    flight_cost = round(distance_km * 10)

    return [

        TransportOption(
            mode="Train",
            estimated_duration=f"{train_duration} hrs",
            estimated_cost=train_cost,
            pros="Affordable and comfortable",
            cons="Fixed schedules"
        ),

        TransportOption(
            mode="Bus",
            estimated_duration=f"{bus_duration} hrs",
            estimated_cost=bus_cost,
            pros="Frequent departures",
            cons="Less comfortable"
        ),

        TransportOption(
            mode="Flight",
            estimated_duration=flight_duration,
            estimated_cost=flight_cost,
            pros="Fastest option",
            cons="Most expensive"
        )
    ]


# ==========================================================
# RECOMMENDATION ENGINE
# ==========================================================

def get_recommendation(
    distance_km,
    budget
):

    if distance_km > 1200:

        if budget >= 5000:

            return (
                "Flight",
                "Very long journey. Flying saves significant time."
            )

        return (
            "Train",
            "Long route but flight exceeds budget."
        )

    elif distance_km > 700:

        if budget >= 4000:

            return (
                "Flight",
                "Flight offers best balance of time and comfort."
            )

        return (
            "Train",
            "Train is more economical."
        )

    elif distance_km > 150:

        return (
            "Train",
            "Best balance of cost, comfort and duration."
        )

    else:

        return (
            "Bus",
            "Most economical option for short distances."
        )


# ==========================================================
# GROQ HUB LOOKUP
# ==========================================================

import re

def get_transport_hubs(
    source,
    destination,
    mode
):

    # Flights use airport lookup already
    if mode == "Flight":
        return {
            "boarding_point": None,
            "arrival_point": None
        }

    try:

        client = Groq(
            api_key=GROQ_API_KEY
        )

        prompt = f"""
You are a transportation expert.

Source City: {source}
Destination City: {destination}
Travel Mode: {mode}

If mode is Train:
Return the most commonly used railway stations.

If mode is Bus:
Return the most commonly used bus terminals.

Return ONLY valid JSON.

Example:

{{
    "boarding_point": "New Delhi Railway Station",
    "arrival_point": "Dehradun Railway Station"
}}

Do not return markdown.
Do not return explanations.
Do not return code fences.
"""

        response = client.chat.completions.create(
            model="openai/gpt-oss-20b",
            temperature=0,
            messages=[
                {
                    "role": "user",
                    "content": prompt
                }
            ]
        )

        content = response.choices[0].message.content

        print("\n========== GROQ RESPONSE ==========")
        print(content)
        print("===================================\n")

        # Extract JSON safely
        match = re.search(
            r"\{.*\}",
            content,
            re.DOTALL
        )

        if match:

            parsed = json.loads(
                match.group()
            )

            return {
                "boarding_point": parsed.get(
                    "boarding_point"
                ),
                "arrival_point": parsed.get(
                    "arrival_point"
                )
            }

        return {
            "boarding_point": None,
            "arrival_point": None
        }

    except Exception as e:

        print(
            f"Groq Hub Lookup Error: {e}"
        )

        return {
            "boarding_point": None,
            "arrival_point": None
        }

# ==========================================================
# MAIN AGENT
# ==========================================================

def transportation_agent(
    source: str,
    destination: str,
    budget: float = 5000
):

    source_coords = geocode_city(source)

    destination_coords = geocode_city(
        destination
    )

    source_airport = get_nearest_airport(
        source_coords[1],
        source_coords[0]
    )

    destination_airport = get_nearest_airport(
        destination_coords[1],
        destination_coords[0]
    )

    distance_km, duration_hr = get_route(
        source_coords,
        destination_coords
    )

    transport_options = generate_transport_options(
        distance_km
    )

    recommended_mode, reason = (
        get_recommendation(
            distance_km,
            budget
        )
    )
    hubs = get_transport_hubs(
        source,
        destination,
        recommended_mode
    )

    source_airport_value = None
    destination_airport_value = None

    boarding_station = None
    arrival_station = None

    boarding_terminal = None
    arrival_terminal = None

    if recommended_mode == "Flight":

        source_airport_value = source_airport
        destination_airport_value = destination_airport

    elif recommended_mode == "Train":

        boarding_station = hubs.get(
            "boarding_point"
        )

        arrival_station = hubs.get(
            "arrival_point"
        )

    elif recommended_mode == "Bus":

        boarding_terminal = hubs.get(
            "boarding_point"
        )

        arrival_terminal = hubs.get(
            "arrival_point"
        )

    result = TransportationOutput(

        source=source,
        destination=destination,

        distance_km=distance_km,
        road_duration_hours=duration_hr,

        recommended_mode=recommended_mode,
        reason=reason,

        source_airport=source_airport_value,
        destination_airport=destination_airport_value,

        boarding_station=boarding_station,
        arrival_station=arrival_station,

        boarding_terminal=boarding_terminal,
        arrival_terminal=arrival_terminal,

        transport_options=transport_options,

        google_flights_url="https://www.google.com/travel/flights",
        skyscanner_url="https://www.skyscanner.com/"
    )

    return result

def transportation_node(state: TravelState):

    result = transportation_agent(
        source=state["source"],
        destination=state["destination"]
    )

    return {
        "transportation": result.model_dump()
    }
    
def weather_node(state: TravelState):

    city = state["city"]
    forecast = get_weather(city)

    return {
        "weather_summary": forecast[0]["condition"] if forecast else "N/A",
        "weather_forecast": forecast
    }
    
from datetime import datetime

def get_trip_days(start_date: str, end_date: str) -> int:
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    if end < start:
        raise ValueError("end_date must be after start_date")

    return (end - start).days + 1

structured_llm = llm.with_structured_output(Itinerary)

from datetime import datetime

def get_trip_days(start_date: str, end_date: str) -> int:
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    if end < start:
        raise ValueError("end_date must be after start_date")

    return (end - start).days + 1


import json
import re

def safe_json_load(text: str):
    """Extract JSON safely from LLM output"""
    try:
        return json.loads(text)
    except:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group())
        raise


def itinerary_node(state: TravelState):

    trip_days = get_trip_days(
        state.get("start_date"),
        state.get("end_date")
    )

    city = state.get("destination") or state.get("city") or "Unknown city"

    prompt = f"""
You are a travel planner AI.

Create a STRICT JSON response only.

Rules:
- Exactly {trip_days} days
- No extra text, no markdown
- Only valid JSON

Format:

{{
  "city": "{city}",
  "days": [
    {{
      "day": 1,
      "title": "string",
      "places": ["..."],
      "activities": ["..."],
      "food": ["..."],
      "notes": ["..."]
    }}
  ]
}}

Trip Info:
City: {city}
Days: {trip_days}
Attractions: {state.get("attractions")}
Restaurants: {state.get("restaurants")}
Weather: {state.get("weather_forecast")}
Safety: {state.get("safety_tips")}
Budget: {state.get("budget")}
Trip Type: {state.get("trip_type")}
"""

    try:
        response = llm.invoke(prompt).content
        itinerary = safe_json_load(response)

    except Exception as e:
        return {
            "itinerary": {
                "city": city,
                "days": [],
                "error": str(e)
            }
        }

    return {
        "itinerary": itinerary
    }

from langchain_core.messages import HumanMessage
import json

def format_itinerary_node(state: TravelState):

    # -----------------------------
    # BUILD SAFE INPUT CONTEXT
    # -----------------------------
    compressed_input = {
        "destination": state.get("destination"),
        "city": state.get("city"),
        "dates": f"{state.get('start_date')} → {state.get('end_date')}",
        "budget": state.get("budget"),
        "trip_type": state.get("trip_type"),
        "interests": state.get("interests"),

        "overview": state.get("overview"),

        "top_attractions": state.get("attractions", []),
        "restaurants": state.get("restaurants", []),
        "hotels": state.get("hotels", []),

        "transport": state.get("transportation", {}),
        "weather": {
            "summary": state.get("weather_summary"),
            "forecast": state.get("weather_forecast", [])
        },

        "safety_tips": state.get("safety_tips", []),

        "itinerary": state.get("itinerary", {})
    }

    # -----------------------------
    # PREMIUM FORMATTER PROMPT
    # -----------------------------
    prompt = f"""
You are an expert travel planner and itinerary designer.

Transform the provided travel data into a PREMIUM, visually appealing, user-friendly travel guide.

IMPORTANT RULES:
- Use ONLY the information provided.
- Do NOT add attractions, restaurants, hotels, activities, timings, or facts that are not present.
- Do NOT remove information.
- Preserve all itinerary details.
- Use emojis and markdown formatting.
- Make the output look like a professional travel application.

OUTPUT FORMAT:

# 🌄 TRIP OVERVIEW
Include:
- Destination
- Travel Dates
- Budget
- Trip Type
- Interests
- Short Overview

# 📍 TOP ATTRACTIONS
Display all attractions.

# 🏨 RECOMMENDED HOTELS
Display hotel name and address.

# 🚗 TRANSPORTATION DETAILS
Include:
- Recommended Mode
- Route
- Distance
- Duration
- Alternative options

# 🌦️ WEATHER INSIGHTS
Include:
- Weather Summary
- Temperature Overview
- Travel Advice

━━━━━━━━━━━━━━━━━━━━

# 🏔️ DAY-WISE EXPERIENCE PLAN

For EVERY DAY use this exact structure:

## Day X: Title

⭐ Highlight of the Day

📍 Places to Visit
- Place 1
- Place 2

🎯 Activities
- Activity 1
- Activity 2
- Activity 3

🍽️ Food Recommendations
- Food item 1
- Food item 2

🕒 Suggested Schedule

🌅 Morning
- Related activities

☀️ Afternoon
- Related activities

🌙 Evening
- Related activities

📝 Notes
- Weather notes
- Special notes

💡 Travel Tip

━━━━━━━━━━━━━━━━━━━━

# 🛡️ SAFETY GUIDELINES

Show all safety tips as bullet points.

DATA:
{json.dumps(compressed_input, indent=2, ensure_ascii=False)}
"""

    # -----------------------------
    # LLM CALL
    # -----------------------------\
    llm1=ChatGroq(model='openai/gpt-oss-120b')
    response = llm1.invoke([
        HumanMessage(content=prompt)
    ])

    # -----------------------------
    # STORE FINAL OUTPUT
    # -----------------------------
    state["formatted_itinerary"] = response.content

    return state

graph = StateGraph(TravelState)

graph.add_node("orchestrator", orchestrator)
graph.add_node("travel_node", travel_node)
graph.add_node("weather_node", weather_node)
graph.add_node("itinerary_node", itinerary_node)
graph.add_node("hotel", hotel_node)
graph.add_node('transportation_node',transportation_node)

graph.add_node('format_itinerary_node',format_itinerary_node)

graph.set_entry_point("orchestrator")

# -----------------------------
# ORCHESTRATOR FAN-OUT
# -----------------------------
graph.add_edge("orchestrator", "travel_node")
graph.add_edge("orchestrator", "weather_node")
graph.add_edge("orchestrator", "hotel")
graph.add_edge("orchestrator", "transportation_node")

graph.add_edge("travel_node", "itinerary_node")
graph.add_edge("weather_node", "itinerary_node")
graph.add_edge("hotel", "itinerary_node")
graph.add_edge("transportation_node", "itinerary_node")

graph.add_edge("itinerary_node", "format_itinerary_node")
graph.add_edge("format_itinerary_node", END)

app = graph.compile()


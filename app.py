import streamlit as st
from datetime import datetime

from main_test_backend import app
from extractor import (
    extract_trip_info,
    get_missing_fields,
    QUESTIONS
)

from db import init_db, save_trip, load_trips

# ==================================================
# DB INIT
# ==================================================
init_db()

# ==================================================
# PAGE CONFIG
# ==================================================
st.set_page_config(
    page_title="AI Travel Planner",
    page_icon="✈️",
    layout="wide"
)

st.title("✈️ AI Travel Planner")

# ==================================================
# SIDEBAR - TRIP HISTORY
# ==================================================
st.sidebar.title("🧳 Your Trips")

if "history" not in st.session_state:
    st.session_state.history = load_trips()

if st.session_state.history:

    for trip in st.session_state.history:

        travel_data = trip.get("travel_data", {})

        source = travel_data.get("source", "Unknown")
        destination = travel_data.get("destination", "Unknown")

        label = f"📍 {source} → {destination}"

        with st.sidebar.expander(label):

            st.write(f"🗓️ {trip['timestamp'][:10]}")

            st.download_button(
                label="📥 Download",
                data=trip["itinerary"],
                file_name=f"{source}_to_{destination}_{trip['id']}.md",
                mime="text/markdown",
                key=f"sb_dl_{trip['id']}"
            )

else:
    st.sidebar.info("No saved trips yet.")

# ==================================================
# SESSION STATE
# ==================================================
if "messages" not in st.session_state:
    st.session_state.messages = []

if "travel_data" not in st.session_state:
    st.session_state.travel_data = {}

if "current_field" not in st.session_state:
    st.session_state.current_field = None

if "final_itinerary" not in st.session_state:
    st.session_state.final_itinerary = None

# ==================================================
# INITIAL MESSAGE
# ==================================================
if len(st.session_state.messages) == 0:
    st.session_state.messages.append({
        "role": "assistant",
        "content": "👋 Hi! Tell me about the trip you want to plan."
    })

# ==================================================
# CHAT DISPLAY
# ==================================================
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ==================================================
# USER INPUT
# ==================================================
user_input = st.chat_input("Describe your trip...")

if user_input:

    st.session_state.messages.append({
        "role": "user",
        "content": user_input
    })

    # ----------------------------------------
    # FIRST EXTRACTION
    # ----------------------------------------
    if not st.session_state.travel_data:

        try:
            extracted = extract_trip_info(user_input)
            extracted_dict = extracted.model_dump()

            for k, v in extracted_dict.items():
                if v:
                    st.session_state.travel_data[k] = v

        except Exception as e:
            st.error(f"Extraction Error:\n{str(e)}")
            st.stop()

    # ----------------------------------------
    # FOLLOW-UP FIELDS
    # ----------------------------------------
    else:
        field = st.session_state.current_field

        if field:
            if field == "interests":
                st.session_state.travel_data[field] = [
                    x.strip() for x in user_input.split(",")
                ]
            else:
                st.session_state.travel_data[field] = user_input

    # ----------------------------------------
    # CHECK MISSING FIELDS
    # ----------------------------------------
    missing = get_missing_fields(st.session_state.travel_data)

    if missing:
        next_field = missing[0]
        st.session_state.current_field = next_field

        st.session_state.messages.append({
            "role": "assistant",
            "content": QUESTIONS[next_field]
        })

        st.rerun()

    # ----------------------------------------
    # GENERATE ITINERARY
    # ----------------------------------------
    st.session_state.current_field = None

    try:
        with st.spinner("Generating your itinerary..."):

            result = app.invoke(st.session_state.travel_data)

        itinerary = result.get(
            "formatted_itinerary",
            "Failed to generate itinerary."
        )

        st.session_state.final_itinerary = itinerary

        # ==================================================
        # SAVE TO SQLITE
        # ==================================================
        save_trip(
            st.session_state.travel_data,
            itinerary
        )

        # refresh sidebar history
        st.session_state.history = load_trips()

        # show in chat
        st.session_state.messages.append({
            "role": "assistant",
            "content": itinerary
        })

        st.rerun()

    except Exception as e:
        st.error(f"Graph Error:\n{str(e)}")

# ==================================================
# DOWNLOAD LATEST TRIP
# ==================================================
if st.session_state.final_itinerary:

    st.divider()
    st.subheader("📥 Download Latest Itinerary")

    source = st.session_state.travel_data.get("source", "trip")
    destination = st.session_state.travel_data.get("destination", "plan")

    st.download_button(
        label="📝 Download Markdown",
        data=st.session_state.final_itinerary,
        file_name=f"{source}_to_{destination}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
        mime="text/markdown"
    )

# ==================================================
# RESET BUTTON
# ==================================================
if st.button("🔄 Start New Trip"):

    st.session_state.messages = []
    st.session_state.travel_data = {}
    st.session_state.current_field = None
    st.session_state.final_itinerary = None

    st.rerun()

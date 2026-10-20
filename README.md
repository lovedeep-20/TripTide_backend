# TripTide Backend

TripTide Backend is the FastAPI server for a travel assistant application. It powers conversational trip planning, session-aware chat, and flight search / booking integrations with multiple travel APIs.

## Overview

The backend is built around a modular FastAPI app and includes:

- LLM-powered travel assistant chat via Groq or OpenAI
- Session memory for multi-turn conversations
- Duplicate-message detection to avoid repeated prompts
- Flight search and location lookup using Amadeus and Sabre
- Provider-based travel search and itinerary utilities
- Health and monitoring endpoints

## Repository structure

```text
TripTide_backend/
├── app/
│   ├── api/
│   │   └── endpoints/
│   │       ├── auth.py
│   │       ├── chat.py
│   │       └── search.py
│   ├── core/
│   │   ├── config.py
│   │   └── logger.py
│   ├── database/
│   │   ├── mongodb.py
│   │   └── postgres.py
│   ├── models/
│   │   ├── itinerary_model.py
│   │   └── user_model.py
│   ├── providers/
│   │   ├── amadeus_provider.py
│   │   ├── pkfare_provider.py
│   │   └── sabre_provider.py
│   ├── schemas/
│   │   ├── base.py
│   │   ├── flight.py
│   │   ├── travel.py
│   │   └── user.py
│   ├── services/
│   │   ├── flight_service.py
│   │   ├── llm_service.py
│   │   └── session_manager.py
│   └── main.py
├── data/
│   ├── Airports_with_IATA.csv
│   └── countries.csv
├── requirements.txt
├── README.md
└── LICENSE
```

## Main application entry point

The app is started from:

- `app/main.py`

It creates the FastAPI application, mounts the `chat` and `search` routers, adds CORS and gzip middleware, and exposes root and health routes.

## API routes

### Core routes

- `GET /` - application metadata
- `GET /health` - health check

### Chat routes

- `POST /api/v1/chat` - send a user message to the travel assistant
- `GET /api/v1/session/{session_id}` - retrieve session metadata
- `DELETE /api/v1/session/{session_id}` - delete a session
- `GET /api/v1/session/{session_id}/debug` - inspect session internals
- `POST /api/v1/session/{session_id}/test-messages` - preview LLM payload generation

### Flight and search routes

- `POST /api/v1/flight/search` - search flights
- `POST /api/v1/location/search` - search locations and airports by keyword
- `POST /api/v1/flight/confirm_price` - price or confirm a flight offer
- `POST /api/v1/flight/booking` - create a booking/order
- `GET /api/v1/flight/order/{order_id}` - fetch order details

> The auth router exists in `app/api/endpoints/auth.py`, but the currently mounted app routers in `app/main.py` are chat and search.

## Features

### Travel assistant chat

The chat flow is built around `LLMService` and stores context in a session manager. It supports:

- multi-turn travel conversation memory
- dynamic provider selection (`groq` and `chatgpt`)
- destination, weather, and recommendation tool workflows
- duplicate query detection based on recent session history

### Flight search

`FlightService` routes flights through provider adapters and normalizes results:

- Amadeus for flight offers and location search
- Sabre as a fallback provider
- return value normalization under a common `data` field

### Config-driven environment setup

Settings are loaded from environment variables in `app/core/config.py`, including:

- `DEFAULT_LLM_PROVIDER`
- `DEFAULT_GROQ_MODEL`
- `DEFAULT_OPENAI_MODEL`
- `GROQ_API_KEY`
- `OPENAI_API_KEY`
- `AMADEUS_API_KEY`
- `AMADEUS_API_SECRET`
- `SABRE_CLIENT_ID`
- `SABRE_CLIENT_SECRET`
- `MONGO_URL`
- `MONGO_DB`
- `GOOGLE_CHAT_WEBHOOK`

## Local development

### 1. Create a virtual environment

```bash
python -m venv .venv
```

On Windows:

```powershell
.venv\Scripts\Activate.ps1
```

On macOS/Linux:

```bash
source .venv/bin/activate
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure environment variables

Create a `.env` file in the project root and include the required values, for example:

```env
DEFAULT_LLM_PROVIDER=groq
DEFAULT_GROQ_MODEL=openai/gpt-oss-20b
DEFAULT_OPENAI_MODEL=gpt-4o-mini
GROQ_API_KEY=your_groq_key
OPENAI_API_KEY=your_openai_key
AMADEUS_API_KEY=your_amadeus_key
AMADEUS_API_SECRET=your_amadeus_secret
AMADEUS_BASE_URL=https://test.api.amadeus.com
SABRE_CLIENT_ID=your_sabre_client_id
SABRE_CLIENT_SECRET=your_sabre_client_secret
SABRE_BASE_URL=your_sabre_base_url
MONGO_URL=mongodb://localhost:27017
MONGO_DB=triptide
SESSION_EXPIRY_MINUTES=30
DUPLICATE_SIMILARITY_THRESHOLD=0.85
DUPLICATE_CHECK_RECENT_MESSAGES=5
```

### 4. Run the API

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Then open:

- `http://localhost:8000/docs` for Swagger UI
- `http://localhost:8000/redoc` for ReDoc

## Example request payloads

### Chat request

```json
{
  "message": "Plan a beach trip to Bali for 5 days",
  "provider": "groq",
  "session_id": "demo-session"
}
```

### Flight search request

```json
{
  "originLocationCode": "JFK",
  "destinationLocationCode": "LHR",
  "departureDate": "2026-11-10",
  "returnDate": "2026-11-17",
  "adults": 1,
  "travelClass": "ECONOMY",
  "nonStop": false,
  "max": 5
}
```

## Notes

- This project is still evolving and includes some experimental or partial integrations.
- The main runtime is centered on the FastAPI application in `app/main.py`.
- Some modules, such as auth and database support, appear to be in progress and may need additional wiring depending on the frontend or deployment setup.

## License

This project is licensed under the terms in the `LICENSE` file.

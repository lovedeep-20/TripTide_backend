from typing import List, Dict, Any, Optional
import json
from groq import Groq
from openai import OpenAI
from app.schemas.base import Message, MessageRole, ToolCall, ProviderConfig, SessionData
from app.schemas.flight import FlightSearchParams
from app.services.flight_service import FlightService
from app.core.config import settings
from app.services.session_manager import session_manager
from app.core.logger import logger


class LLMService:
    """
    Improved LLM Service with proper history management following best practices:
    1. Store COMPLETE conversation turns (including tool calls & results)
    2. Replay history in the EXACT format the API expects
    3. Use conversation summaries for very long conversations
    4. Handle function context intelligently
    """
    
    def __init__(self):
        self.available_functions = {
            "confirm_destination": self.confirm_destination,
            "get_travel_recommendations": self.get_travel_recommendations,
            "get_weather_forecast": self.get_weather_forecast,
            "search_flights": self.search_flights,
        }
        
        # Function definitions for the LLM
        self.function_schemas = [
            {
                "name": "confirm_destination",
                "description": "Confirm the travel destination with the user",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "destination": {
                            "type": "string",
                            "description": "The destination location (city, country)"
                        },
                        "check_in": {
                            "type": "string",
                            "description": "Check-in date in YYYY-MM-DD format"
                        },
                        "check_out": {
                            "type": "string",
                            "description": "Check-out date in YYYY-MM-DD format"
                        },
                        "purpose": {
                            "type": "string",
                            "description": "Purpose of the trip (e.g., vacation, business, honeymoon)",
                            "enum": ["vacation", "business", "honeymoon", "family", "solo", "adventure", "other"],
                            "default": "vacation"
                        }
                    },
                    "required": ["destination"]
                }
            },
            {
                "name": "get_travel_recommendations",
                "description": "Get travel recommendations based on user preferences",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "destination": {
                            "type": "string",
                            "description": "The destination location"
                        },
                        "interests": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "List of interests (e.g., beaches, hiking, history)"
                        },
                        "budget_level": {
                            "type": "string",
                            "enum": ["budget", "mid-range", "luxury"],
                            "description": "Budget level for the trip"
                        }
                    },
                    "required": ["destination"]
                }
            },
            {
                "name": "get_weather_forecast",
                "description": "Get weather forecast for a specific location and date range",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "location": {
                            "type": "string",
                            "description": "City and country for weather forecast"
                        },
                        "start_date": {
                            "type": "string",
                            "description": "Start date in YYYY-MM-DD format"
                        },
                        "end_date": {
                            "type": "string",
                            "description": "End date in YYYY-MM-DD format"
                        }
                    },
                    "required": ["location"]
                }
            }
            ,
            {
                "name": "search_flights",
                "description": "Search for flights between two airports",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "originLocationCode": {"type": "string", "description": "IATA code of origin airport"},
                        "destinationLocationCode": {"type": "string", "description": "IATA code of destination airport"},
                        "departureDate": {"type": "string", "description": "Departure date in YYYY-MM-DD"},
                        "returnDate": {"type": "string", "description": "Return date in YYYY-MM-DD"},
                        "adults": {"type": "integer", "description": "Number of adult passengers"},
                        "children": {"type": "integer"},
                        "infants": {"type": "integer"},
                        "travelClass": {"type": "string", "description": "Travel class: ECONOMY, BUSINESS, FIRST, PREMIUM_ECONOMY"},
                        "nonStop": {"type": "boolean"},
                        "currencyCode": {"type": "string"},
                        "max": {"type": "integer", "description": "Max number of results to return"}
                    },
                    "required": ["originLocationCode", "destinationLocationCode", "departureDate", "adults"]
                }
            }
        ]
        
        # Initialize providers
        self.providers = {
            "groq": ProviderConfig(
                name="groq",
                api_key=settings.GROQ_API_KEY,
                model=settings.DEFAULT_GROQ_MODEL
            ),
            "chatgpt": ProviderConfig(
                name="chatgpt",
                api_key=settings.OPENAI_API_KEY,
                model=settings.DEFAULT_OPENAI_MODEL
            )
        }

    # Friendly system persona for the assistant
    SYSTEM_PROMPT = (
        "You are a friendly, professional travel assistant. You can:\n"
        "- Confirm travel destinations and dates\n"
        "- Provide travel recommendations\n"
        "- Get weather forecasts\n\n"
        "Use the available tools when needed. Remember context from previous messages. "
        "Greet users warmly, be concise, and maintain context throughout the conversation. "
        "When user says inspire me then search for popular desitnations and ask for their interests. "
        "Help users plan if they have no specific destination and ask helpful follow-up questions "
        "to clarify travel needs (dates, budget, companions, interests). "
        "When you've confirmed a destination or dates earlier, reference them in follow-up responses. "
        "Always keep the answers short and concise."
        "Ask user if they want to book flights after confirming their destination. "
        "If needed end responses with a short 'You might want to ask' list of 3 suggested follow-ups."
    )

    def build_messages_for_api(self, session: SessionData, max_history: int = 20) -> List[Dict[str, Any]]:
        """
        Build messages in the exact format the API expects.
        This is the KEY function for proper history management.
        """
        messages = []
        
        # 1. System prompt (always first)
        messages.append({
            "role": "system",
            "content": self.SYSTEM_PROMPT
        })
        
        # 2. Add session metadata as context if available
        if session.metadata:
            context = self._build_context_from_metadata(session.metadata)
            if context:
                messages.append({
                    "role": "system",
                    "content": f"Context from previous conversation: {context}"
                })
        
        # 3. Get recent history and convert to API format
        recent_messages = session.get_recent_messages(max_history)
        for msg in recent_messages:
            messages.append(msg.to_api_format())
        
        logger.info(f"Built {len(messages)} messages for API (including system prompts)")
        logger.info(f"Messages: {[{'role': m['role'], 'content': str(m.get('content', ''))[:50] + '...' if len(str(m.get('content', ''))) > 50 else str(m.get('content', ''))} for m in messages]}")
        
        return messages

    def _build_context_from_metadata(self, metadata: Dict[str, Any]) -> str:
        """Build a context string from session metadata"""
        context_parts = []
        if "destination" in metadata:
            context_parts.append(f"Destination: {metadata['destination']}")
        if "check_in" in metadata:
            context_parts.append(f"Check-in: {metadata['check_in']}")
        if "check_out" in metadata:
            context_parts.append(f"Check-out: {metadata['check_out']}")
        if "purpose" in metadata:
            context_parts.append(f"Purpose: {metadata['purpose']}")
        return ", ".join(context_parts)


# -------------------------------------------------- uncomment this function to use the previous version

    # async def process_message(self, session: SessionData, user_message: str, provider_name: str = "groq") -> str:
    #     """
    #     Process a user message with full history awareness.
    #     This is the MAIN function that orchestrates everything.
    #     """
    #     # 1. Add user message to session
    #     session.add_user_message(user_message)
        
    #     # 2. Build messages with full history
    #     messages = self.build_messages_for_api(session)
        
    #     # 3. Get provider and make API call
    #     provider = self.providers.get(provider_name, self.providers["groq"])
    #     client = Groq(api_key=provider.api_key)
        
    #     response = client.chat.completions.create(
    #         model=provider.model,
    #         messages=messages,
    #         tools=[{"type": "function", "function": f} for f in self.function_schemas],
    #         tool_choice="auto",
    #         temperature=0.7,
    #         max_tokens=1024,
    #     )
        
    #     response_message = response.choices[0].message
        
    #     # 4. Handle tool calls if present
    #     if response_message.tool_calls:
    #         # Add assistant message with tool calls to session
    #         tool_calls = [
    #             ToolCall(
    #                 id=tc.id,
    #                 type="function",
    #                 function={
    #                     "name": tc.function.name,
    #                     "arguments": tc.function.arguments
    #                 }
    #             )
    #             for tc in response_message.tool_calls
    #         ]
            
    #         session.add_assistant_message(
    #             content=response_message.content,
    #             tool_calls=tool_calls
    #         )
            
    #         # Execute functions and add results to session
    #         for tool_call in response_message.tool_calls:
    #             function_name = tool_call.function.name
    #             function_args = json.loads(tool_call.function.arguments)
                
    #             # Execute function
    #             if function_name in self.available_functions:
    #                 # Call the mapped function (e.g., search_flights will validate args)
    #                 result = await self.available_functions[function_name](**function_args)
                    
    #                 # Update session metadata if this was a confirmation
    #                 if function_name == "confirm_destination" and "details" in result:
    #                     for key, value in result["details"].items():
    #                         if value:  # Only store non-empty values
    #                             session.update_metadata(key, value)
                    
    #                 # Add tool result to session
    #                 session.add_tool_message(
    #                     tool_call_id=tool_call.id,
    #                     name=function_name,
    #                     content=json.dumps(result)
    #                 )
            
    #         # Get final response with tool results
    #         messages = self.build_messages_for_api(session)
    #         final_response = client.chat.completions.create(
    #             model=provider.model,
    #             messages=messages,
    #             temperature=0.7,
    #             max_tokens=1024,
    #         )
            
    #         final_content = final_response.choices[0].message.content
    #         session.add_assistant_message(content=final_content)
    #         return final_content
        
    #     # 5. No tool calls - just add response to session
    #     session.add_assistant_message(content=response_message.content)
    #     return response_message.content

# -------------------------------------------------- new version with minor changes
    async def process_message(
    self,
    session: SessionData,
    user_message: str,
    provider_name: str = "groq"
    ) -> str:
        """
        Process a user message with full history awareness.
        Works with both Groq and OpenAI.
        """

        # 1. Add user message to session
        session.add_user_message(user_message)

        # 2. Build messages including full session history
        messages = self.build_messages_for_api(session)

        # 3. Get provider config
        provider = self.providers.get(provider_name, self.providers["groq"])

        # 4. Select client based on provider
        if provider.name == "groq":
            client = Groq(api_key=provider.api_key)
        else:
            client = OpenAI(api_key=provider.api_key)

        # 5. First response
        response = client.chat.completions.create(
            model=provider.model,
            messages=messages,
            tools=[{"type": "function", "function": f} for f in self.function_schemas],
            tool_choice="auto",
            temperature=0.7,
            max_tokens=1024,
        )

        response_message = response.choices[0].message

        # ---------------------------------------------------
        # 6. Handle Tool Calls (same flow for Groq + OpenAI)
        # ---------------------------------------------------
        if response_message.tool_calls:

            tool_calls = [
                ToolCall(
                    id=tc.id,
                    type="function",
                    function={
                        "name": tc.function.name,
                        "arguments": tc.function.arguments
                    }
                )
                for tc in response_message.tool_calls
            ]

            # Add assistant message with tool_call metadata
            session.add_assistant_message(
                content=response_message.content,
                tool_calls=tool_calls
            )

            # Execute each tool call
            for tool_call in response_message.tool_calls:

                function_name = tool_call.function.name
                function_args = json.loads(tool_call.function.arguments)

                # Call mapped function
                if function_name in self.available_functions:
                    result = await self.available_functions[function_name](**function_args)

                    # Optional: store meta updates in session
                    if function_name == "confirm_destination" and "details" in result:
                        for key, value in result["details"].items():
                            if value:
                                session.update_metadata(key, value)

                    # Add tool result to session
                    session.add_tool_message(
                        tool_call_id=tool_call.id,
                        name=function_name,
                        content=json.dumps(result)
                    )

            # ---------------------------------------------------
            # 7. Get final response AFTER providing tool results
            # ---------------------------------------------------
            messages = self.build_messages_for_api(session)

            final_response = client.chat.completions.create(
                model=provider.model,
                messages=messages,
                temperature=0.7,
                max_tokens=1024,
            )

            final_content = final_response.choices[0].message.content
            session.add_assistant_message(content=final_content)
            return final_content

        # ---------------------------------------------------
        # 8. No tool calls → Direct Assistant Response
        # ---------------------------------------------------
        session.add_assistant_message(content=response_message.content)
        return response_message.content

    # Legacy methods for backward compatibility
    def build_messages_for_provider(self, session_id: Optional[str], user_message: str, max_history: int = 12) -> List[Dict[str, Any]]:
        """Legacy method - use process_message instead"""
        if not session_id:
            return [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": user_message}
            ]
        
        session = session_manager.get_session(session_id)
        if not session:
            return [
                {"role": "system", "content": self.SYSTEM_PROMPT},
                {"role": "user", "content": user_message}
            ]
        
        return self.build_messages_for_api(session, max_history)

    async def send_to_provider(self, messages: List[Dict[str, Any]], provider_name: str = "groq") -> dict:
        """Legacy method - use process_message instead"""
        provider = self.providers.get(provider_name, self.providers["groq"])
        client = Groq(api_key=provider.api_key)
        
        response = client.chat.completions.create(
            model=provider.model,
            messages=messages,
            tools=[{"type": "function", "function": func} for func in self.function_schemas],
            tool_choice="auto",
            temperature=0.7,
            max_tokens=1024,
        )
        
        return {"response": response.choices[0].message.content, "function_call_messages": []}

    # Function implementations
    async def confirm_destination(
        self,
        destination: str,
        check_in: Optional[str] = None,
        check_out: Optional[str] = None,
        purpose: Optional[str] = None
    ) -> dict:
        """Confirm travel destination with the user"""
        return {
            "status": "success",
            "message": f"Destination confirmed: {destination}",
            "details": {
                "destination": destination,
                "check_in": check_in,
                "check_out": check_out,
                "purpose": purpose or "Not specified"
            }
        }
    
    async def get_travel_recommendations(
        self,
        destination: str,
        interests: Optional[List[str]] = None,
        budget_level: Optional[str] = None
    ) -> dict:
        """Get travel recommendations for a destination"""
        return {
            "status": "success",
            "destination": destination,
            "recommendations": [
                {
                    "type": "attraction",
                    "name": f"Top attraction in {destination}",
                    "description": f"A must-visit place in {destination}",
                    "cost": "$" if budget_level == "budget" else "$$",
                    "tags": interests or []
                }
            ]
        }
    
    async def get_weather_forecast(
        self,
        location: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None
    ) -> dict:
        """Get weather forecast for a location"""
        return {
            "status": "success",
            "location": location,
            "forecast": {
                "temperature": "25°C",
                "conditions": "Sunny",
                "date_range": f"{start_date} to {end_date}" if start_date and end_date else "Next 7 days"
            }
        }

    async def search_flights(self, **kwargs) -> dict:
        """Validate incoming args and call FlightService to search flights."""
        try:
            params = FlightSearchParams(**kwargs)
        except Exception as e:
            return {"status": "error", "error": "invalid_parameters", "details": str(e)}

        svc = FlightService()
        results = await svc.search_flights(params)

        # Optionally update metadata with origin/destination/dates
        # Return normalized result
        return {"status": "success", "count": len(results.get("data", [])), "results": results.get("data", [])}
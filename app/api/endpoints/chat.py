from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from app.schemas.base import Message, ChatRequest, ChatResponse, MessageRole
from app.services.llm_service import LLMService
from app.core.config import settings
from app.services.session_manager import session_manager
from app.core.logger import logger


router = APIRouter()
llm_service = LLMService()

@router.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    """
    Handle chat messages with the travel assistant.
    
    This endpoint processes natural language messages and returns the assistant's response,
    maintaining conversation history in the session.
    """
    try:
        # Get or create session (supports custom session IDs)
        session_id, session = session_manager.get_or_create_session(request.session_id)

        # Check for duplicate messages before processing (only if session has messages)
        if len(session.messages) > 0:
            is_duplicate, duplicate_user_msg, previous_response = session_manager.check_for_duplicate_message(
                session_id, request.message
            )
            
            if is_duplicate and previous_response:
                # Generate a smart response acknowledging the duplicate
                duplicate_response = (
                    f"I notice you asked something similar just now. "
                    f"As I mentioned before: {previous_response.content[:200]}{'...' if len(previous_response.content) > 200 else ''}\n\n"
                    f"Would you like me to provide more details about this, or do you have a different question? "
                    f"I can also help you with related topics if you'd like to explore further."
                )
                
                # Save both the duplicate user message and the acknowledgment response
                session.add_user_message(request.message)
                session.add_assistant_message(content=duplicate_response)
                
                logger.info(f"Duplicate message detected in session {session_id}. Original: '{duplicate_user_msg.content}', New: '{request.message}'")
                return ChatResponse(response=duplicate_response, provider=request.provider, session_id=session_id)

        # Short-circuit common greetings with a warm assistant intro
        if request.message.strip().lower() in {"hi", "hello", "hey", "hi there", "hello!"}:
            greeting_content = (
                "Hello! 👋\n\n"
                "Welcome! Whether you're looking for recommendations or simply planning a trip, I am here to help you craft the perfect travel experience. "
            )
            session.add_user_message(request.message)
            session.add_assistant_message(content=greeting_content)
            return ChatResponse(response=greeting_content, provider=request.provider, session_id=session_id)

        # Use the new improved process_message method
        provider_response_text = await llm_service.process_message(session, request.message, request.provider)

        # Log full conversation history for debugging/traceability
        if session:
            lines = []
            for m in session.get_conversation_history(9999):
                # format: [ROLE] timestamp: content
                ts = getattr(m, "timestamp", None)
                lines.append(f"[{m.role.value}] {ts}: {m.content}")
            logger.info("Full conversation for session %s:\n%s", session_id, "\n".join(lines))

        return ChatResponse(response=provider_response_text, provider=request.provider, session_id=session_id)

    except Exception as e:
        logger.error(f"Chat endpoint error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/session/{session_id}")
async def get_session(session_id: str):
    """Get the current state of a session"""
    session = session_manager.get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    
    return {
        "session_id": session.session_id,
        "created_at": session.created_at,
        "last_accessed": session.last_accessed,
        "message_count": len(session.messages)
    }

@router.delete("/session/{session_id}")
async def delete_session(session_id: str):
    """Delete a session"""
    if session_manager.delete_session(session_id):
        return {"status": "success", "message": "Session deleted"}
    raise HTTPException(status_code=404, detail="Session not found")

@router.get("/session/{session_id}/debug")
async def get_session_debug(session_id: str):
    """Get detailed debug information about a session"""
    debug_info = session_manager.get_session_debug_info(session_id)
    if "error" in debug_info:
        raise HTTPException(status_code=404, detail=debug_info["error"])
    return debug_info

@router.post("/session/{session_id}/test-messages")
async def test_message_building(session_id: str, test_message: str = "What should I pack?"):
    """Test what messages would be sent to the LLM provider for a given input"""
    try:
        messages_payload = llm_service.build_messages_for_provider(session_id, test_message)
        return {
            "session_id": session_id,
            "test_message": test_message,
            "messages_payload": messages_payload,
            "total_messages": len(messages_payload)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
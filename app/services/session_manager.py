from datetime import datetime, timedelta
from typing import Dict, Optional, List, Tuple
import uuid
import re
from difflib import SequenceMatcher
from app.schemas.base import SessionData, Message, MessageRole
from app.core.config import settings
import asyncio

class SessionManager:
    _instance = None
    _sessions: Dict[str, SessionData] = {}
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SessionManager, cls).__new__(cls)
            cls._instance._cleanup_task = asyncio.create_task(cls._instance._cleanup_old_sessions())
        return cls._instance
    
    async def _cleanup_old_sessions(self):
        """Background task to clean up old sessions"""
        while True:
            await asyncio.sleep(60 * 5)  # Check every 5 minutes
            now = datetime.utcnow()
            expired_sessions = [
                session_id for session_id, session in self._sessions.items()
                if now - session.last_accessed > timedelta(minutes=settings.SESSION_EXPIRY_MINUTES)
            ]
            for session_id in expired_sessions:
                del self._sessions[session_id]
    
    def create_session(self, custom_session_id: str = None) -> str:
        """Create a new session and return its ID"""
        session_id = custom_session_id or str(uuid.uuid4())
        self._sessions[session_id] = SessionData(session_id=session_id)
        return session_id
    
    def get_or_create_session(self, session_id: str = None) -> tuple[str, SessionData]:
        """Get existing session or create new one. Returns (session_id, session_object)"""
        if session_id and session_id in self._sessions:
            # Update last accessed time
            self._sessions[session_id].last_accessed = datetime.utcnow()
            return session_id, self._sessions[session_id]
        
        # Create new session (with custom ID if provided)
        new_session_id = self.create_session(session_id)
        return new_session_id, self._sessions[new_session_id]
    
    def get_session(self, session_id: str) -> Optional[SessionData]:
        """Get a session by ID, updating its last_accessed time"""
        if session_id in self._sessions:
            self._sessions[session_id].last_accessed = datetime.utcnow()
            return self._sessions[session_id]
        return None
    
    def add_message_to_session(self, session_id: str, role: MessageRole, content: str, name: str = None) -> bool:
        """Add a message to a session's history"""
        if session_id not in self._sessions:
            return False
        
        message = Message(role=role, content=content, name=name)
        self._sessions[session_id].add_message(message)
        
        # Log the addition for debugging
        from app.core.logger import logger
        logger.info(f"Added message to session {session_id}: [{role.value}] {content[:100]}...")
        logger.info(f"Session {session_id} now has {len(self._sessions[session_id].messages)} messages")
        
        return True
    
    def get_session_messages(self, session_id: str, max_messages: int = 10) -> List[Message]:
        """Get the message history for a session"""
        if session_id not in self._sessions:
            return []
        
        return self._sessions[session_id].get_conversation_history(max_messages)
    
    def delete_session(self, session_id: str) -> bool:
        """Delete a session"""
        if session_id in self._sessions:
            del self._sessions[session_id]
            return True
        return False
    
    def get_session_debug_info(self, session_id: str) -> dict:
        """Get detailed debug information about a session"""
        if session_id not in self._sessions:
            return {"error": "Session not found"}
        
        session = self._sessions[session_id]
        return {
            "session_id": session.session_id,
            "created_at": session.created_at.isoformat(),
            "last_accessed": session.last_accessed.isoformat(),
            "message_count": len(session.messages),
            "messages": [
                {
                    "role": msg.role.value,
                    "content": msg.content[:100] + "..." if len(msg.content) > 100 else msg.content,
                    "name": msg.name,
                    "timestamp": msg.timestamp.isoformat()
                }
                for msg in session.messages
            ]
        }
    
    def _normalize_message(self, message: str) -> str:
        """Normalize a message for comparison by removing extra whitespace, punctuation, and converting to lowercase"""
        # Remove extra whitespace and convert to lowercase
        normalized = re.sub(r'\s+', ' ', message.strip().lower())
        # Remove common punctuation
        normalized = re.sub(r'[.,!?;:]', '', normalized)
        return normalized
    
    def _calculate_similarity(self, msg1: str, msg2: str) -> float:
        """Calculate similarity between two messages using SequenceMatcher"""
        norm1 = self._normalize_message(msg1)
        norm2 = self._normalize_message(msg2)
        return SequenceMatcher(None, norm1, norm2).ratio()
    
    def check_for_duplicate_message(self, session_id: str, new_message: str, similarity_threshold: float = None, recent_messages_count: int = None) -> Tuple[bool, Optional[Message], Optional[Message]]:
        """
        Check if the new message is similar to recent messages in the session.
        
        Args:
            session_id: The session to check
            new_message: The new message to compare
            similarity_threshold: Minimum similarity ratio to consider a duplicate (0.0-1.0), uses config default if None
            recent_messages_count: Number of recent messages to check, uses config default if None
            
        Returns:
            Tuple of (is_duplicate, duplicate_user_message, assistant_response)
        """
        # Use config defaults if not provided
        if similarity_threshold is None:
            similarity_threshold = settings.DUPLICATE_SIMILARITY_THRESHOLD
        if recent_messages_count is None:
            recent_messages_count = settings.DUPLICATE_CHECK_RECENT_MESSAGES
        if session_id not in self._sessions:
            return False, None, None
        
        session = self._sessions[session_id]
        messages = session.messages
        
        # Get recent user messages and their responses
        recent_pairs = []
        for i in range(len(messages) - 1, -1, -1):
            if messages[i].role == MessageRole.USER:
                # Find the next assistant message after this user message
                assistant_response = None
                for j in range(i + 1, len(messages)):
                    if messages[j].role == MessageRole.ASSISTANT:
                        assistant_response = messages[j]
                        break
                
                recent_pairs.append((messages[i], assistant_response))
                
                # Stop when we have enough recent pairs
                if len(recent_pairs) >= recent_messages_count:
                    break
        
        # Check similarity with recent user messages
        for user_msg, assistant_msg in recent_pairs:
            similarity = self._calculate_similarity(new_message, user_msg.content)
            if similarity >= similarity_threshold:
                return True, user_msg, assistant_msg
        
        return False, None, None

# Global session manager instance
session_manager = SessionManager()

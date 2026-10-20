from pydantic import BaseModel, Field
from typing import List, Literal, Optional, Dict, Any, Union
from datetime import datetime, timedelta
from enum import Enum

class MessageRole(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    TOOL = "tool"  # Use "tool" not "function" for OpenAI/Groq API

class ToolCall(BaseModel):
    """Represents a tool call made by the assistant"""
    id: str
    type: str = "function"
    function: Dict[str, Any]  # {"name": "...", "arguments": "..."}

class Message(BaseModel):
    """Complete message representation that preserves all context"""
    role: MessageRole
    content: Optional[str] = None
    name: Optional[str] = None  # For tool messages
    tool_calls: Optional[List[ToolCall]] = None  # For assistant messages
    tool_call_id: Optional[str] = None  # For tool response messages
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    def to_api_format(self) -> Dict[str, Any]:
        """Convert to API-compatible format"""
        msg = {"role": self.role.value}
        
        if self.content:
            msg["content"] = self.content
            
        if self.tool_calls:
            msg["tool_calls"] = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function": tc.function
                }
                for tc in self.tool_calls
            ]
            
        if self.tool_call_id:
            msg["tool_call_id"] = self.tool_call_id
            
        if self.name:
            msg["name"] = self.name
            
        return msg

class ChatRequest(BaseModel):
    message: str
    provider: Literal["groq", "chatgpt"] = "groq"
    session_id: Optional[str] = None  # For maintaining conversation context

class ChatResponse(BaseModel):
    response: str
    provider: str
    session_id: str  # Always return a session ID
    function_call: Optional[Dict[str, Any]] = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
class FunctionCall(BaseModel):
    name: str
    arguments: Dict[str, Any]

class SessionData(BaseModel):
    """Represents a conversation session with the assistant"""
    session_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_accessed: datetime = Field(default_factory=datetime.utcnow)
    messages: List[Message] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)  # Store extracted info (destination, dates, etc.)
    
    def add_message(self, message: Message):
        """Add a message to the session and update last_accessed"""
        self.messages.append(message)
        self.last_accessed = datetime.utcnow()
    
    def add_user_message(self, content: str):
        """Helper to add user message"""
        message = Message(
            role=MessageRole.USER,
            content=content,
            timestamp=datetime.utcnow()
        )
        self.add_message(message)
    
    def add_assistant_message(self, content: Optional[str] = None, tool_calls: Optional[List[ToolCall]] = None):
        """Helper to add assistant message"""
        message = Message(
            role=MessageRole.ASSISTANT,
            content=content,
            tool_calls=tool_calls,
            timestamp=datetime.utcnow()
        )
        self.add_message(message)
    
    def add_tool_message(self, tool_call_id: str, name: str, content: str):
        """Helper to add tool result message"""
        message = Message(
            role=MessageRole.TOOL,
            tool_call_id=tool_call_id,
            name=name,
            content=content,
            timestamp=datetime.utcnow()
        )
        self.add_message(message)
    
    def update_metadata(self, key: str, value: Any):
        """Update session metadata (e.g., confirmed destination, dates)"""
        self.metadata[key] = value
    
    def get_conversation_history(self, max_messages: int = 15) -> List[Message]:
        """Get the most recent messages, limited by max_messages"""
        return self.messages[-max_messages:]
    
    def get_recent_messages(self, limit: int = 20) -> List[Message]:
        """Get recent messages for context window management"""
        return self.messages[-limit:] if len(self.messages) > limit else self.messages
    
    def is_expired(self, expiry_minutes: int = 30) -> bool:
        """Check if the session has expired"""
        return (datetime.utcnow() - self.last_accessed) > timedelta(minutes=expiry_minutes)

class ProviderConfig(BaseModel):
    """Configuration for LLM providers"""
    name: str
    api_key: str
    model: str
    
    class Config:
        frozen = True  # Make the config immutable

class ErrorResponse(BaseModel):
    """Standard error response format"""
    error: str
    details: Optional[Dict[str, Any]] = None
    code: int = 400

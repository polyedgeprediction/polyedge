"""
Standard API response POJOs for consistent response structure.
"""
from dataclasses import dataclass
from typing import Any, Dict, Optional
from datetime import datetime


@dataclass
class ApiResponse:
    """Standard API response structure"""
    success: bool
    message: str
    data: Optional[Any] = None
    timestamp: Optional[datetime] = None
    executionTime: Optional[float] = None

    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()

    def toDict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        result = {
            'success': self.success,
            'message': self.message,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None
        }
        
        if self.data is not None:
            result['data'] = self.data
            
        if self.executionTime is not None:
            result['executionTime'] = f"{self.executionTime:.3f}s"
            
        return result

    @staticmethod
    def success(message: str, data: Any = None) -> 'ApiResponse':
        """Create successful response"""
        return ApiResponse(success=True, message=message, data=data)

    @staticmethod
    def error(message: str, data: Any = None) -> 'ApiResponse':
        """Create error response"""
        return ApiResponse(success=False, message=message, data=data)
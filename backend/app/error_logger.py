from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
import logging
import json
from .models import BaseModel

class ErrorType(str, Enum):
    API_LIMIT = "api_limit"
    NETWORK_ERROR = "network_error"
    TRADING_ERROR = "trading_error"
    AUTHENTICATION_ERROR = "auth_error"
    DATA_ERROR = "data_error"
    SYSTEM_ERROR = "system_error"

class ErrorLog(BaseModel):
    id: Optional[str] = None
    error_type: ErrorType
    message: str
    details: Dict[str, Any] = {}
    timestamp: datetime
    resolved: bool = False
    severity: str = "medium"

class ErrorLogger:
    """
    Enhanced error logging system for production monitoring
    and dashboard error display
    """
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.error_history: List[ErrorLog] = []
        self.max_history = 100
    
    def log_error(
        self, 
        error_type: ErrorType, 
        message: str, 
        details: Dict[str, Any] = None,
        severity: str = "medium"
    ) -> ErrorLog:
        """Log an error with structured data"""
        error_log = ErrorLog(
            id=f"err_{int(datetime.now().timestamp())}",
            error_type=error_type,
            message=message,
            details=details or {},
            timestamp=datetime.now(),
            severity=severity
        )
        
        self.error_history.append(error_log)
        if len(self.error_history) > self.max_history:
            self.error_history.pop(0)
        
        log_level = {
            "low": logging.INFO,
            "medium": logging.WARNING,
            "high": logging.ERROR,
            "critical": logging.CRITICAL
        }.get(severity, logging.WARNING)
        
        self.logger.log(
            log_level,
            f"[{error_type.value}] {message}",
            extra={"error_details": details}
        )
        
        return error_log
    
    def get_recent_errors(self, limit: int = 20) -> List[ErrorLog]:
        """Get recent errors for dashboard display"""
        return sorted(
            self.error_history[-limit:], 
            key=lambda x: x.timestamp, 
            reverse=True
        )
    
    def get_unresolved_errors(self) -> List[ErrorLog]:
        """Get unresolved errors"""
        return [err for err in self.error_history if not err.resolved]
    
    def resolve_error(self, error_id: str) -> bool:
        """Mark an error as resolved"""
        for error in self.error_history:
            if error.id == error_id:
                error.resolved = True
                return True
        return False
    
    def get_error_stats(self) -> Dict[str, Any]:
        """Get error statistics for monitoring"""
        total_errors = len(self.error_history)
        unresolved_count = len(self.get_unresolved_errors())
        
        error_counts = {}
        for error in self.error_history:
            error_counts[error.error_type.value] = error_counts.get(error.error_type.value, 0) + 1
        
        return {
            "total_errors": total_errors,
            "unresolved_errors": unresolved_count,
            "error_types": error_counts,
            "last_error": self.error_history[-1].timestamp if self.error_history else None
        }

error_logger = ErrorLogger()

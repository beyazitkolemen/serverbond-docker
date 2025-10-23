"""
Production-ready logging module
"""
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional

class ServerBondLogger:
    """Production-ready logger for ServerBond Agent"""
    
    def __init__(self, name: str = "serverbond-agent", log_level: str = "INFO"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(getattr(logging, log_level.upper()))
        
        # Clear existing handlers
        self.logger.handlers.clear()
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        
        # File handler
        log_dir = Path("/var/log/serverbond")
        log_dir.mkdir(exist_ok=True)
        
        file_handler = logging.FileHandler(log_dir / "agent.log")
        file_handler.setLevel(logging.DEBUG)
        
        # Error file handler
        error_handler = logging.FileHandler(log_dir / "agent-error.log")
        error_handler.setLevel(logging.ERROR)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        
        console_handler.setFormatter(formatter)
        file_handler.setFormatter(formatter)
        error_handler.setFormatter(formatter)
        
        # Add handlers
        self.logger.addHandler(console_handler)
        self.logger.addHandler(file_handler)
        self.logger.addHandler(error_handler)
    
    def info(self, message: str, **kwargs):
        """Log info message"""
        self.logger.info(message, extra=kwargs)
    
    def warning(self, message: str, **kwargs):
        """Log warning message"""
        self.logger.warning(message, extra=kwargs)
    
    def error(self, message: str, **kwargs):
        """Log error message"""
        self.logger.error(message, extra=kwargs)
    
    def debug(self, message: str, **kwargs):
        """Log debug message"""
        self.logger.debug(message, extra=kwargs)
    
    def critical(self, message: str, **kwargs):
        """Log critical message"""
        self.logger.critical(message, extra=kwargs)

# Global logger instance
logger = ServerBondLogger()

def log(message: str, level: str = "INFO", **kwargs):
    """Convenience function for logging"""
    getattr(logger, level.lower())(message, **kwargs)

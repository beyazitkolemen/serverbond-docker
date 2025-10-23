"""
Security validation and hardening module
"""
import re
import secrets
import string
from typing import Optional, Dict, Any
from urllib.parse import urlparse
from fastapi import HTTPException

class SecurityValidator:
    """Security validation utilities"""
    
    @staticmethod
    def validate_domain(domain: str) -> bool:
        """Validate domain name"""
        if not domain or len(domain) > 253:
            return False
        
        # Basic domain regex
        domain_pattern = r'^[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9\-]{0,61}[a-zA-Z0-9])?)*$'
        return bool(re.match(domain_pattern, domain))
    
    @staticmethod
    def validate_repo_url(repo: str) -> bool:
        """Validate repository URL"""
        try:
            parsed = urlparse(repo)
            if parsed.scheme not in ['http', 'https', 'git']:
                return False
            
            # Check for common git hosting services
            allowed_hosts = [
                'github.com', 'gitlab.com', 'bitbucket.org',
                'git.sr.ht', 'codeberg.org'
            ]
            
            if parsed.netloc not in allowed_hosts:
                return False
                
            return True
        except:
            return False
    
    @staticmethod
    def validate_php_version(version: str) -> bool:
        """Validate PHP version"""
        valid_versions = ['8.0', '8.1', '8.2', '8.3', '8.4']
        return version in valid_versions
    
    @staticmethod
    def validate_framework(framework: str) -> bool:
        """Validate framework type"""
        valid_frameworks = ['laravel', 'laravel-inertia', 'nextjs', 'nuxt', 'nodeapi', 'static']
        return framework in valid_frameworks
    
    @staticmethod
    def sanitize_filename(filename: str) -> str:
        """Sanitize filename for security"""
        # Remove dangerous characters
        dangerous_chars = ['..', '/', '\\', ':', '*', '?', '"', '<', '>', '|']
        for char in dangerous_chars:
            filename = filename.replace(char, '_')
        
        # Limit length
        return filename[:100]
    
    @staticmethod
    def generate_secure_token(length: int = 32) -> str:
        """Generate secure random token"""
        return secrets.token_urlsafe(length)
    
    @staticmethod
    def validate_password_strength(password: str) -> bool:
        """Validate password strength"""
        if len(password) < 8:
            return False
        
        # Check for at least one uppercase, lowercase, digit
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        
        return has_upper and has_lower and has_digit
    
    @staticmethod
    def validate_input_data(data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and sanitize input data"""
        validated = {}
        
        for key, value in data.items():
            if isinstance(value, str):
                # Basic XSS protection
                value = value.replace('<', '&lt;').replace('>', '&gt;')
                value = value.replace('"', '&quot;').replace("'", '&#x27;')
                validated[key] = value
            else:
                validated[key] = value
        
        return validated

def validate_build_request(data: Dict[str, Any]) -> None:
    """Validate build request data"""
    errors = []
    
    # Required fields
    if not data.get('repo'):
        errors.append("Repository URL is required")
    elif not SecurityValidator.validate_repo_url(data['repo']):
        errors.append("Invalid repository URL")
    
    if not data.get('domain'):
        errors.append("Domain is required")
    elif not SecurityValidator.validate_domain(data['domain']):
        errors.append("Invalid domain name")
    
    # Optional fields validation
    if data.get('framework') and not SecurityValidator.validate_framework(data['framework']):
        errors.append("Invalid framework type")
    
    if data.get('php_version') and not SecurityValidator.validate_php_version(data['php_version']):
        errors.append("Invalid PHP version")
    
    if errors:
        raise HTTPException(400, f"Validation errors: {', '.join(errors)}")

def validate_token(token: str) -> bool:
    """Validate agent token"""
    if not token:
        return False
    
    # Token should be at least 32 characters
    if len(token) < 32:
        return False
    
    # Token should contain only safe characters
    safe_chars = string.ascii_letters + string.digits + '-_'
    return all(c in safe_chars for c in token)

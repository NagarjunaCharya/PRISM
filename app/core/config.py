from pydantic_settings import BaseSettings
from typing import Optional
import os

class Settings(BaseSettings):
    PROJECT_NAME: str = "SIIH2026 AI Safety System"
    
    # LDAP Configuration
    LDAP_SERVER: str = "ldap://mock-ldap-server:389"
    LDAP_BIND_DN: str = "cn=admin,dc=example,dc=com"
    LDAP_BIND_PASSWORD: str = "admin_pass"
    LDAP_USER_SEARCH_BASE: str = "ou=users,dc=example,dc=com"
    
    # Security Configuration
    JWT_ALGORITHM: str = "RS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    
    # AI External APIs
    NVIDIA_API_KEY: Optional[str] = None
    
    # RS256 Keys path
    PRIVATE_KEY_PATH: str = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "keys", "private_key.pem")
    PUBLIC_KEY_PATH: str = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "keys", "public_key.pem")
    
    # Lockout Policy
    MAX_LOGIN_ATTEMPTS: int = 5
    LOCKOUT_DURATION_MINUTES: int = 60

    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()

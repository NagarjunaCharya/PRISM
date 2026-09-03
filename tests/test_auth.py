import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from fastapi import FastAPI
import time

from app.db.database import Base, get_db
from app.db.models import User, UserRole
from app.api.v1.auth import router as auth_router
from app.api.v1.users import router as users_router
from app.services.user_service import create_user

# Setup test DB
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_auth.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Setup test app
app = FastAPI()
app.include_router(auth_router, prefix="/api/v1/auth")
app.include_router(users_router, prefix="/api/v1/users")

def override_get_db():
    try:
        db = TestingSessionLocal()
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_get_db
client = TestClient(app)

@pytest.fixture(autouse=True)
def setup_db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    # Create test users
    create_user(db, "local_admin", "admin@test.com", "password123", UserRole.ADMIN)
    create_user(db, "local_viewer", "viewer@test.com", "password123", UserRole.VIEWER)
    db.close()
    yield
    Base.metadata.drop_all(bind=engine)

def test_ldap_mock_login():
    """Test the mocked LDAP authentication."""
    response = client.post(
        "/api/v1/auth/login",
        data={"username": "admin", "password": "admin"}
    )
    assert response.status_code == 200
    assert "access_token" in response.json()

def test_local_login():
    """Test local DB authentication."""
    response = client.post(
        "/api/v1/auth/login",
        data={"username": "local_admin", "password": "password123"}
    )
    assert response.status_code == 200
    assert "access_token" in response.json()

def test_local_login_failure_and_lockout():
    """Test that 5 failed attempts lock the account."""
    for _ in range(5):
        response = client.post(
            "/api/v1/auth/login",
            data={"username": "local_viewer", "password": "wrongpassword"}
        )
        assert response.status_code == 401
    
    # 6th attempt with correct password should still fail because it's locked
    response = client.post(
        "/api/v1/auth/login",
        data={"username": "local_viewer", "password": "password123"}
    )
    assert response.status_code == 401
    assert "account locked" in response.json()["detail"]

def test_rbac_access():
    """Test Role-Based Access Control decorators."""
    # 1. Login as local admin
    res = client.post("/api/v1/auth/login", data={"username": "local_admin", "password": "password123"})
    token = res.json()["access_token"]
    
    # 2. Access admin endpoint (should succeed)
    admin_res = client.post("/api/v1/users/admin-only", headers={"Authorization": f"Bearer {token}"})
    assert admin_res.status_code == 200
    
    # 3. Login as viewer
    res2 = client.post("/api/v1/auth/login", data={"username": "local_viewer", "password": "password123"})
    token2 = res2.json()["access_token"]
    
    # 4. Access admin endpoint (should fail)
    admin_res2 = client.post("/api/v1/users/admin-only", headers={"Authorization": f"Bearer {token2}"})
    assert admin_res2.status_code == 403
    assert admin_res2.json()["detail"] == "Operation not permitted"

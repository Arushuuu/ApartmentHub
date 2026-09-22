from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
import os
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.database import get_db
from app.models import Tenant
from app.schemas import TenantCreate, TenantResponse, Token

router = APIRouter(prefix="/auth", tags=["Authentication"])

# JWT Configuration
SECRET_KEY = os.getenv("JWT_SECRET_KEY")
if not SECRET_KEY:
    raise RuntimeError("JWT_SECRET_KEY is not set. Add it to backend/.env.")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def get_current_tenant(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> Tenant:
    credentials_error = HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token", headers={"WWW-Authenticate": "Bearer"})
    try:
        tenant_id = int(jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM]).get("sub"))
    except (JWTError, TypeError, ValueError):
        raise credentials_error
    tenant = db.get(Tenant, tenant_id)
    if tenant is None:
        raise credentials_error
    return tenant

def create_access_token(data: dict, expires_delta: timedelta | None = None):
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=15))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

@router.post("/signup", response_model=TenantResponse, status_code=status.HTTP_201_CREATED)
def signup(tenant_data: TenantCreate, db: Session = Depends(get_db)):
    existing_tenant = db.query(Tenant).filter(Tenant.t_email == tenant_data.t_email).first()
    if existing_tenant:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    hashed_pwd = get_password_hash(tenant_data.password)
    new_tenant = Tenant(
        tenant_name=tenant_data.tenant_name,
        t_email=tenant_data.t_email,
        password_hash=hashed_pwd,
        t_dob=tenant_data.t_dob,
        t_phone_no=tenant_data.t_phone_no
    )
    db.add(new_tenant)
    db.commit()
    db.refresh(new_tenant)
    return new_tenant

@router.post("/login", response_model=Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    tenant = db.query(Tenant).filter(Tenant.t_email == form_data.username).first()
    if not tenant or not verify_password(form_data.password, tenant.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    access_token = create_access_token(
        data={"sub": str(tenant.tenant_id)},
        expires_delta=timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    return {"access_token": access_token, "token_type": "bearer"}
@router.get("/users/me", response_model=TenantResponse)
def read_users_me(current_tenant: Tenant = Depends(get_current_tenant)):
    return current_tenant

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.database import engine, Base
from app.routers import account, auth, leases, tickets, utilities

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Apartment Rental & Rent Splitting Portal API")

app.add_middleware(
    CORSMiddleware,
    # Vite selects the next available port when 5173 is already in use.
    # Permit local development servers without opening CORS to public sites.
    allow_origins=[],
    allow_origin_regex=r"^http://(localhost|127\.0\.0\.1):\d+$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(account.router)
app.include_router(leases.router)
app.include_router(tickets.router)
app.include_router(utilities.router)

@app.get("/")
def read_root():
    return {"message": "Apartment Portal API is running"}

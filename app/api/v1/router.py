from fastapi import APIRouter

from app.api.v1 import advertising_consents, account, auth, availability, calls, chats, health, matching, policy_consents, profile, safety

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(account.router, tags=["account"])
api_router.include_router(profile.router, tags=["profile"])
api_router.include_router(policy_consents.router, tags=["policy-consents"])
api_router.include_router(advertising_consents.router, tags=["advertising-consent"])
api_router.include_router(safety.router, tags=["safety"])
api_router.include_router(availability.router, tags=["availability"])
api_router.include_router(matching.router, tags=["matching"])
api_router.include_router(calls.router, tags=["calls"])
api_router.include_router(chats.router, tags=["chats"])

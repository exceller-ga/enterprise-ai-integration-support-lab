from fastapi import FastAPI

app = FastAPI(title="Outlook Simulator")

@app.get("/health")
async def health():
    return {
        "service": "outlook-sim",
        "status": "ok"
    }

@app.get("/messages")
async def messages():
    return {
        "messages": [
            {
                "id": 1,
                "from": "manager@example.com",
                "subject": "Weekly platform review"
            },
            {
                "id": 2,
                "from": "support@example.com",
                "subject": "Incident follow-up"
            }
        ]
    }

from fastapi import Header, HTTPException
import jwt
from jwt import PyJWKClient


KEYCLOAK_ISSUER = "http://keycloak:8080/realms/awsquick-lab"

JWKS_URL = (
    "http://keycloak:8080/realms/awsquick-lab/"
    "protocol/openid-connect/certs"
)

jwks_client = PyJWKClient(JWKS_URL)


@app.get("/secure-messages")
async def secure_messages(
    authorization: str | None = Header(default=None)
):

    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Missing access token"
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Invalid authorization header"
        )

    access_token = authorization.split(" ", 1)[1]

    try:
        signing_key = jwks_client.get_signing_key_from_jwt(
            access_token
        )

        claims = jwt.decode(
            access_token,
            signing_key.key,
            algorithms=["RS256"],
            audience="account",
            issuer=KEYCLOAK_ISSUER
        )

    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail="Access token expired"
        )

    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=401,
            detail="Invalid access token"
        )

    client_roles = claims.get(
        "resource_access",
        {}
    ).get(
        "awsquick-connector",
        {}
    ).get(
        "roles",
        []
    )

    if "outlook.read" not in client_roles:
        raise HTTPException(
            status_code=403,
            detail="outlook.read permission required"
        )

    return {
        "user": claims.get("preferred_username"),
        "permission": "outlook.read",
        "messages": [
            {
                "id": 101,
                "from": "platform@example.com",
                "subject": "Secure Outlook message"
            }
        ]
    }

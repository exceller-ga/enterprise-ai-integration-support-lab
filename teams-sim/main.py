from fastapi import FastAPI

app = FastAPI(title="Teams Simulator")

@app.get("/health")
async def health():
    return {
        "service": "teams-sim",
        "status": "ok"
    }

@app.get("/channels")
async def channels():
    return {
        "channels": [
            {
                "id": 1,
                "name": "Platform Support"
            },
            {
                "id": 2,
                "name": "Incident Response"
            }
        ]
    }


from fastapi import Header, HTTPException
import jwt
from jwt import PyJWKClient


KEYCLOAK_ISSUER = "http://keycloak:8080/realms/awsquick-lab"

JWKS_URL = (
    "http://keycloak:8080/realms/"
    "awsquick-lab/protocol/openid-connect/certs"
)

jwks_client = PyJWKClient(JWKS_URL)


def verify_keycloak_token(authorization: str | None):

    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Missing access token"
        )

    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Invalid Authorization header"
        )

    token = authorization.removeprefix("Bearer ").strip()

    try:
        signing_key = jwks_client.get_signing_key_from_jwt(token)

        claims = jwt.decode(
            token,
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

    except jwt.InvalidTokenError as exc:
        raise HTTPException(
            status_code=401,
            detail=f"Invalid access token: {exc}"
        )

    return claims


@app.get("/manager-area")
async def manager_area(
    authorization: str | None = Header(default=None)
):

    claims = verify_keycloak_token(authorization)

    roles = claims.get(
        "realm_access",
        {}
    ).get(
        "roles",
        []
    )

    if "manager" not in roles:
        raise HTTPException(
            status_code=403,
            detail="Manager role required"
        )

    return {
        "message": "Teams manager access granted",
        "username": claims.get("preferred_username"),
        "roles": roles,
        "issued_at": claims.get("iat"),
        "expires_at": claims.get("exp")
    }

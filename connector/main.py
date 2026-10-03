import os
import base64
import json
from fastapi.responses import RedirectResponse
from fastapi.responses import HTMLResponse
from fastapi import FastAPI, Request, HTTPException
from starlette.middleware.sessions import SessionMiddleware
from authlib.integrations.starlette_client import OAuth

app = FastAPI()

app.add_middleware(
    SessionMiddleware,
    secret_key=os.environ["SESSION_SECRET"]
)

oauth = OAuth()

oauth.register(
    name="keycloak",
    client_id="awsquick-connector",
    server_metadata_url="http://keycloak:8080/realms/awsquick-lab/.well-known/openid-configuration",
    client_kwargs={"scope": "openid profile"}
)

#
#@app.get("/")
#def home():
#    return {"message": "AWS Quick Connector is running"}
#
KEYCLOAK_URL = "http://keycloak:8080"
KEYCLOAK_REALM = "awsquick-lab"

LAB_ADMIN_USER = os.getenv("KEYCLOAK_ADMIN_USERNAME", "admin")
LAB_ADMIN_PASSWORD = os.environ["KEYCLOAK_ADMIN_PASSWORD"]

TARGET_USER = os.getenv("TARGET_USER", "employee01")
TARGET_USER_ID = os.environ["TARGET_USER_ID"]

CONNECTOR_CLIENT_UUID = os.environ["CONNECTOR_CLIENT_UUID"]

OUTLOOK_ROLE = "outlook.read"


async def get_keycloak_admin_token():

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{KEYCLOAK_URL}/realms/master/protocol/openid-connect/token",
            data={
                "grant_type": "password",
                "client_id": "admin-cli",
                "username": LAB_ADMIN_USER,
                "password": LAB_ADMIN_PASSWORD
            }
        )

    if response.status_code != 200:
        raise HTTPException(
            status_code=500,
            detail="Could not get Keycloak admin token"
        )

    return response.json()["access_token"]


async def get_outlook_role(admin_token):

    async with httpx.AsyncClient() as client:
        response = await client.get(
            f"{KEYCLOAK_URL}/admin/realms/"
            f"{KEYCLOAK_REALM}/clients/"
            f"{CONNECTOR_CLIENT_UUID}/roles/"
            f"{OUTLOOK_ROLE}",
            headers={
                "Authorization": f"Bearer {admin_token}"
            }
        )

    if response.status_code != 200:
        raise HTTPException(
            status_code=500,
            detail="Could not find outlook.read role"
        )

    return response.json()


@app.get("/", response_class=HTMLResponse)
def home():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Enterprise AI Workspace</title>
        <style>
            body {
                font-family: Arial, sans-serif;
                background: #f4f6f8;
                margin: 0;
            }
            header {
                background: #182a3a;
                color: white;
                padding: 22px 40px;
            }
            header h1 {
                margin: 0;
                font-size: 24px;
            }
            header p {
                margin: 5px 0 0;
                color: #cbd5df;
            }
            .container {
                max-width: 900px;
                margin: 60px auto;
                background: white;
                padding: 40px;
                border-radius: 10px;
                box-shadow: 0 3px 12px rgba(0,0,0,.10);
            }
            .login {
                display: inline-block;
                background: #146eb4;
                color: white;
                text-decoration: none;
                padding: 13px 24px;
                border-radius: 6px;
                margin: 15px 0 30px;
            }
            .services {
                display: flex;
                gap: 15px;
            }
            .service {
                flex: 1;
                border: 1px solid #ddd;
                padding: 18px;
                border-radius: 7px;
            }
            .status {
                color: #68737d;
                font-size: 14px;
            }
        </style>
    </head>

    <body>
        <header>
            <h1>Enterprise AI Workspace</h1>
            <p>Support Integration Lab</p>
        </header>

        <div class="container">
            <h2>Welcome</h2>
            <p>Access enterprise services through secure SSO.</p>

            <a class="login" href="/login">Sign in with Enterprise SSO</a>

            <h3>Connected Services</h3>

            <div class="services">
                <div class="service">
                    <strong>Outlook</strong>
                    <p class="status">Enterprise Mail</p>
                </div>

                <div class="service">
                    <strong>Teams</strong>
                    <p class="status">Collaboration</p>
                </div>

                <div class="service">
                    <strong>Snowflake</strong>
                    <p class="status">Enterprise Data</p>
                </div>
            </div>
        </div>
    </body>
    </html>
    """


@app.get("/login")
async def login(request: Request):
    redirect_uri = "http://192.168.40.129:8000/callback"
    return await oauth.keycloak.authorize_redirect(request, redirect_uri)

@app.get("/callback")
async def callback(request: Request):
    token = await oauth.keycloak.authorize_access_token(request)
    request.session["access_token"] = token["access_token"]

    user = token.get("userinfo")

    access_token = token.get("access_token")
    payload = access_token.split(".")[1]
    payload += "=" * (-len(payload) % 4)
    claims = json.loads(base64.urlsafe_b64decode(payload))

    roles = claims.get("realm_access", {}).get("roles", [])

    request.session["username"] = user.get("preferred_username")
    request.session["roles"] = roles

    return RedirectResponse(
        url="/dashboard",
        status_code=302
    )

@app.get("/manager-test")
async def manager_test(request: Request):
    roles = request.session.get("roles", [])

    if "manager" not in roles:
        raise HTTPException(
            status_code=403,
            detail="Manager role required"
        )

    return {
        "message": "Manager access granted",
        "username": request.session.get("username"),
        "roles": roles
    }

import httpx


@app.get("/outlook-test")
async def outlook_test():
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "http://outlook-sim:8100/messages"
        )

    return {
        "connector": "awsquick-connector",
        "target": "outlook-sim",
        "status_code": response.status_code,
        "data": response.json()
    }


@app.get("/teams-test")
async def teams_test():
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "http://teams-sim:8200/channels"
        )

    return {
        "connector": "awsquick-connector",
        "target": "teams-sim",
        "status_code": response.status_code,
        "data": response.json()
    }


@app.get("/snowflake-test")
async def snowflake_test():
    async with httpx.AsyncClient() as client:
        response = await client.get(
            "http://snowflake-sim:8300/query"
        )

    return {
        "connector": "awsquick-connector",
        "target": "snowflake-sim",
        "status_code": response.status_code,
        "data": response.json()
    }


def require_login(request: Request):
    username = request.session.get("username")

    if not username:
        raise HTTPException(
            status_code=401,
            detail="Authentication required"
        )

    return username


@app.get("/app/outlook")
async def app_outlook(request: Request):
    username = require_login(request)

    access_token = request.session.get("access_token")

    if not access_token:
        raise HTTPException(
            status_code=401,
            detail="Access token not found"
        )

    async with httpx.AsyncClient() as client:
        response = await client.get(
            "http://outlook-sim:8100/secure-messages",
            headers={
                "Authorization": f"Bearer {access_token}"
            }
        )

    result = {
        "connector_user": username,
        "target": "outlook-sim",
        "downstream_status": response.status_code,
        "downstream_response": response.json()
    }

    return Response(
        content=json.dumps(
            result,
            indent=2
        ),
        status_code=response.status_code,
        media_type="application/json"
    )

@app.get("/app/teams")
async def app_teams(request: Request):
    username = require_login(request)

    async with httpx.AsyncClient() as client:
        response = await client.get(
            "http://teams-sim:8200/channels"
        )

    return {
        "user": username,
        "target": "teams-sim",
        "status_code": response.status_code,
        "data": response.json()
    }


@app.get("/app/snowflake")
async def app_snowflake(
    request: Request,
    mode: str = "normal"
):

    username = require_login(request)

    if mode not in [
        "normal",
        "slow",
        "timeout"
    ]:
        raise HTTPException(
            status_code=400,
            detail="Invalid Snowflake mode"
        )

    start_time = time.perf_counter()

    try:

        async with httpx.AsyncClient(
            timeout=3.0
        ) as client:

            response = await client.get(
                "http://snowflake-sim:8300/query",
                params={
                    "mode": mode
                }
            )

        elapsed = round(
            time.perf_counter() - start_time,
            2
        )

        result = {
            "connector_user": username,
            "target": "snowflake-sim",
            "mode": mode,
            "downstream_status":
                response.status_code,
            "elapsed_seconds":
                elapsed,
            "downstream_response":
                response.json()
        }

        return Response(
            content=json.dumps(
                result,
                indent=2
            ),
            status_code=response.status_code,
            media_type="application/json"
        )

    except httpx.TimeoutException:

        elapsed = round(
            time.perf_counter() - start_time,
            2
        )

        result = {
            "connector_user": username,
            "target": "snowflake-sim",
            "mode": mode,
            "downstream_status": "TIMEOUT",
            "elapsed_seconds": elapsed,
            "connector_timeout_seconds": 3.0,
            "detail":
                "Upstream Snowflake request timed out"
        }

        return Response(
            content=json.dumps(
                result,
                indent=2
            ),
            status_code=504,
            media_type="application/json"
        )

@app.get("/app/outlook-bad-token")
async def app_outlook_bad_token(request: Request):
    username = require_login(request)

    headers = {
        "Authorization": "Bearer intentionally-invalid-token"
    }

    async with httpx.AsyncClient() as client:
        response = await client.get(
            "http://outlook-sim:8100/secure-messages",
            headers=headers
        )

    return {
        "user": username,
        "target": "outlook-sim",
        "downstream_status": response.status_code,
        "downstream_response": response.json()
    }

import base64
import json
import time


@app.get("/debug/token-info")
async def token_info(request: Request):
    username = require_login(request)
    access_token = request.session.get("access_token")

    if not access_token:
        raise HTTPException(
            status_code=401,
            detail="Access token not found"
        )

    payload = access_token.split(".")[1]
    payload += "=" * (-len(payload) % 4)

    claims = json.loads(
        base64.urlsafe_b64decode(payload).decode()
    )

    result = {
        "username_from_session": username,

        "token_claims": {
            "preferred_username": claims.get("preferred_username"),
            "sub": claims.get("sub"),
            "iss": claims.get("iss"),
            "aud": claims.get("aud"),
            "azp": claims.get("azp"),
            "scope": claims.get("scope"),
            "roles": claims.get(
                "realm_access",
                {}
            ).get(
                "roles",
                []
            ),
            "client_roles": claims.get(
            "resource_access",
                {}
            ).get(
                "awsquick-connector",
                {}
            ).get(
                "roles",
                []
            ),
            "iat": claims.get("iat"),
            "exp": claims.get("exp"),
            "expired_now":
                int(time.time()) >= claims.get("exp", 0)
        }
    }

    return Response(
        content=json.dumps(
            result,
            indent=2
        ),
        media_type="application/json"
    )


from fastapi.responses import Response


@app.get("/app/teams-secure")
async def app_teams_secure(request: Request):

    username = require_login(request)

    access_token = request.session.get(
        "access_token"
    )

    if not access_token:
        raise HTTPException(
            status_code=401,
            detail="Access token not found"
        )

    headers = {
        "Authorization": f"Bearer {access_token}"
    }

    async with httpx.AsyncClient() as client:

        response = await client.get(
            "http://teams-sim:8200/manager-area",
            headers=headers
        )

    result = {
        "connector_user": username,

        "target": "teams-sim",

        "downstream_status":
            response.status_code,

        "downstream_response":
            response.json()
    }

    return Response(
        content=json.dumps(
            result,
            indent=2
        ),
        status_code=response.status_code,
        media_type="application/json"
    )

@app.post("/admin/outlook/grant")
async def grant_outlook_role(request: Request):

    require_login(request)

    admin_token = await get_keycloak_admin_token()
    role = await get_outlook_role(admin_token)

    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{KEYCLOAK_URL}/admin/realms/"
            f"{KEYCLOAK_REALM}/users/"
            f"{TARGET_USER_ID}/role-mappings/clients/"
            f"{CONNECTOR_CLIENT_UUID}",
            headers={
                "Authorization": f"Bearer {admin_token}"
            },
            json=[role]
        )

    if response.status_code != 204:
        raise HTTPException(
            status_code=500,
            detail=f"Grant failed: {response.text}"
        )

    return {
        "action": "grant",
        "user": TARGET_USER,
        "role": OUTLOOK_ROLE,
        "status": "success",
        "message": "Get a new access token to see the new permission."
    }


@app.post("/admin/outlook/remove")
async def remove_outlook_role(request: Request):

    require_login(request)

    admin_token = await get_keycloak_admin_token()
    role = await get_outlook_role(admin_token)

    async with httpx.AsyncClient() as client:
        response = await client.request(
            "DELETE",
            f"{KEYCLOAK_URL}/admin/realms/"
            f"{KEYCLOAK_REALM}/users/"
            f"{TARGET_USER_ID}/role-mappings/clients/"
            f"{CONNECTOR_CLIENT_UUID}",
            headers={
                "Authorization": f"Bearer {admin_token}"
            },
            json=[role]
        )

    if response.status_code != 204:
        raise HTTPException(
            status_code=500,
            detail=f"Remove failed: {response.text}"
        )

    return {
        "action": "remove",
        "user": TARGET_USER,
        "role": OUTLOOK_ROLE,
        "status": "success",
        "message": "Get a new access token to see the permission change."
    }

@app.post("/lab/reset-outlook")
async def reset_outlook_lab(request: Request):

    require_login(request)

    admin_token = await get_keycloak_admin_token()
    role = await get_outlook_role(admin_token)

    async with httpx.AsyncClient() as client:
        response = await client.request(
            "DELETE",
            f"{KEYCLOAK_URL}/admin/realms/"
            f"{KEYCLOAK_REALM}/users/"
            f"{TARGET_USER_ID}/role-mappings/clients/"
            f"{CONNECTOR_CLIENT_UUID}",
            headers={
                "Authorization": f"Bearer {admin_token}"
            },
            json=[role]
        )

    if response.status_code != 204:
        raise HTTPException(
            status_code=500,
            detail=f"Reset failed: {response.text}"
        )

    return RedirectResponse(
        url="/login",
        status_code=303
    )

@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard(request: Request):

    username = require_login(request)

    roles = request.session.get("roles", [])

    access_token = request.session.get("access_token")

    if not access_token:
        raise HTTPException(
            status_code=401,
            detail="Access token not found"
        )

    payload = access_token.split(".")[1]
    payload += "=" * (-len(payload) % 4)

    claims = json.loads(
        base64.urlsafe_b64decode(payload).decode()
    )

    issued_at = claims.get("iat")
    expires_at = claims.get("exp")

    expired = int(time.time()) >= expires_at

    roles_html = "<br>".join(roles)

    return f"""
    <html>

    <head>
        <title>AWS Quick Support Lab</title>
    </head>

    <body>

        <h1>AWS Quick Support Lab</h1>

        <div
    style="
        border: 1px solid #aaa;
        padding: 15px;
        margin-bottom: 25px;
        font-size: 20px;
    "
>
    <div>
        <b>Current Time:</b>
        <span id="current-time">Loading...</span>
    </div>

    <div>
        <b>Token Expires At:</b>
        <span id="expiry-time">Loading...</span>
    </div>

    <div>
        <b>Token Lifetime:</b>
        20 seconds
    </div>
</div>

        <h2>Current Session</h2>

        <p>
            <b>User:</b>
            {username}
        </p>

        <p>
            <b>Issued:</b>
            {issued_at}
        </p>

        <p>
            <b>Expires:</b>
            {expires_at}
        </p>

        <p>
            <b>Expired:</b>
            {expired}
        </p>

        <p>
            <b>Roles:</b><br>
            {roles_html}
        </p>

        <hr>

        <h2>Access Token Remaining</h2>

        <div
            id="token-timer"
            style="
                font-size: 64px;
                font-weight: bold;
                margin: 25px 0;
            "
        >
            Loading...
        </div>

        <hr>

        <h2>Lab Control</h2>

        <form action="/lab/reset-outlook" method="post">
            <button type="submit">
                Reset Outlook Lab
            </button>
        </form>

        <p>
            Removes outlook.read and starts with a new access token.
        </p>

        <hr>

        <h2>Outlook Permission Control</h2>

        <button onclick="changeOutlookRole('/admin/outlook/grant')">
            Grant outlook.read
        </button>

        <button onclick="changeOutlookRole('/admin/outlook/remove')">
            Remove outlook.read
        </button>

        <p>
            Permission changes apply to the next access token.
        </p>

        <hr>

        <h2>Application Tests</h2>

        <button onclick="loadService('/app/outlook')">
            Outlook
        </button>

        <button onclick="loadService('/app/teams-secure')">
            Teams Secure
        </button>

        <button onclick="loadService('/app/snowflake?mode=normal')">
            Snowflake Normal
        </button>

        <button onclick="loadService('/app/snowflake?mode=slow')">
            Snowflake Slow
        </button>

        <button onclick="loadService('/app/snowflake?mode=timeout')">
            Snowflake Timeout
        </button>

        <hr>

        <h2>Service Result</h2>

        <div>
            <b>HTTP Status:</b>
            <span id="service-status">
                -
            </span>
        </div>

        <pre
            id="service-result"
            style="
                border: 1px solid #aaa;
                padding: 15px;
                margin-top: 10px;
                min-height: 180px;
                white-space: pre-wrap;
            "
        >
        Select a service above.
        </pre>

        <p>
            <a
                href="/debug/token-info"
                target="_blank"
            >
                View Token Claims
            </a>
        </p>

        <p>
            <a
                href="/login"
            >
                Get New Access Token
            </a>
        </p>

        <script>

            const expiresAt = {expires_at};

            const currentTimeDisplay =
            document.getElementById(
            "current-time"
            );

            const expiryTimeDisplay =
                document.getElementById(
                    "expiry-time"
                );

            expiryTimeDisplay.textContent =
                new Date(
                    expiresAt * 1000
                ).toLocaleTimeString();

                function updateTimer() {{

                const now =
                    Math.floor(
                        Date.now() / 1000
                    );
                currentTimeDisplay.textContent =
                    new Date().toLocaleTimeString();
                const remaining =
                    Math.max(
                        0,
                        expiresAt - now
                    );

                const timer =
                    document.getElementById(
                        "token-timer"
                    );

                if (remaining > 0) {{

                    timer.textContent =
                        remaining + " seconds";

                }} else {{

                    timer.textContent =
                        "EXPIRED";

                }}
            }}

            updateTimer();

            setInterval(
                updateTimer,
                1000
            );



        async function changeOutlookRole(url) {{

        const statusBox =
            document.getElementById(
                "service-status"
            );

        const resultBox =
            document.getElementById(
                "service-result"
            );

        statusBox.textContent =
            "Changing permission...";

        resultBox.textContent =
            "Requesting " + url;

        try {{

            const response =
                await fetch(
                    url,
                    {{
                        method: "POST"
                    }}
                );

            const text =
                await response.text();

            statusBox.textContent =
                response.status;

            try {{

                const data =
                    JSON.parse(text);

                resultBox.textContent =
                    JSON.stringify(
                        data,
                        null,
                        2
                    );

            }} catch {{

                resultBox.textContent =
                    text;
            }}

            }} catch (error) {{

                statusBox.textContent =
                    "ERROR";

                resultBox.textContent =
                    error.toString();
            }}
        }}

                async function loadService(url) {{

                const statusBox =
                    document.getElementById(
                        "service-status"
                    );

                const resultBox =
                    document.getElementById(
                        "service-result"
                    );

                statusBox.textContent =
                    "Loading...";

                resultBox.textContent =
                    "Requesting " + url;

                try {{

                    const response =
                        await fetch(url);

                    const text =
                        await response.text();

                    statusBox.textContent =
                        response.status;

                    try {{

                        const data =
                            JSON.parse(text);

                        resultBox.textContent =
                            JSON.stringify(
                                data,
                                null,
                                2
                            );

                    }} catch {{

                        resultBox.textContent =
                            text;
                    }}

                }} catch (error) {{

                    statusBox.textContent =
                        "ERROR";

                    resultBox.textContent =
                        error.toString();
                }}
            }}

        </script>

    </body>

    </html>
    """

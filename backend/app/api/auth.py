from __future__ import annotations

import traceback

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import HTMLResponse, RedirectResponse
from itsdangerous import BadSignature, URLSafeSerializer

from app.core.config import settings
from app.integrations.google_oauth import (
    create_authorization_url,
    fetch_google_userinfo,
    fetch_tokens_from_callback,
)

router = APIRouter(prefix="/auth/google", tags=["auth"])

state_signer = URLSafeSerializer(settings.secret_key, salt="google-oauth-state")


@router.get("/start")
async def google_auth_start() -> RedirectResponse:
    signed_state = state_signer.dumps({"provider": "google"})
    authorization_url, _ = create_authorization_url(state=signed_state)
    return RedirectResponse(url=authorization_url, status_code=302)


@router.get("/callback", response_class=HTMLResponse)
async def google_auth_callback(
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
) -> HTMLResponse:
    try:
        if error:
            raise HTTPException(status_code=400, detail=f"Google OAuth error: {error}")

        if not code or not state:
            raise HTTPException(status_code=400, detail="Missing code or state.")

        try:
            state_signer.loads(state)
        except BadSignature as exc:
            raise HTTPException(status_code=400, detail="Invalid OAuth state.") from exc

        token_data = fetch_tokens_from_callback(code=code, state=state)
        userinfo = await fetch_google_userinfo(token_data["token"])

        html = f"""
        <html>
          <head>
            <title>Google Connected</title>
            <style>
              body {{
                font-family: Arial, sans-serif;
                max-width: 720px;
                margin: 40px auto;
                line-height: 1.5;
              }}
              .card {{
                border: 1px solid #ddd;
                border-radius: 12px;
                padding: 20px;
              }}
              code {{
                background: #f4f4f4;
                padding: 2px 6px;
                border-radius: 6px;
              }}
            </style>
          </head>
          <body>
            <div class="card">
              <h1>Google account connected</h1>
              <p><strong>Email:</strong> {userinfo.get("email", "unknown")}</p>
              <p><strong>Name:</strong> {userinfo.get("name", "unknown")}</p>
              <p><strong>Access token received:</strong> {"yes" if token_data.get("token") else "no"}</p>
              <p><strong>Refresh token received:</strong> {"yes" if token_data.get("refresh_token") else "no"}</p>
              <p><strong>Scopes granted:</strong></p>
              <ul>
                {''.join(f"<li><code>{scope}</code></li>" for scope in token_data.get("scopes", []))}
              </ul>
            </div>
          </body>
        </html>
        """
        return HTMLResponse(content=html)

    except HTTPException:
        raise
    except Exception as exc:
        tb = traceback.format_exc()
        print(tb)
        return HTMLResponse(
            content=f"""
            <html>
              <body style="font-family: Arial; max-width: 900px; margin: 40px auto;">
                <h1>OAuth callback failed</h1>
                <p><strong>Error:</strong> {type(exc).__name__}: {str(exc)}</p>
                <pre style="white-space: pre-wrap; background: #f4f4f4; padding: 16px; border-radius: 8px;">{tb}</pre>
              </body>
            </html>
            """,
            status_code=500,
        )
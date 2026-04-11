"""Google authentication routes.

These endpoints start the Google OAuth flow and handle the callback that
stores the connected account and tokens in the database.
"""
# backend/app/api/auth.py
from __future__ import annotations

import secrets
import traceback
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from itsdangerous import BadSignature, URLSafeSerializer
from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import get_db
from app.integrations.google_oauth import (
    create_authorization_url,
    fetch_google_userinfo,
    fetch_tokens_from_callback,
)
from app.models import GoogleAccount, User

router = APIRouter(prefix="/auth/google", tags=["auth"])

state_signer = URLSafeSerializer(settings.secret_key, salt="google-oauth-state")


@router.get("/start")
async def google_auth_start(request: Request) -> RedirectResponse:
    signed_state = state_signer.dumps({"provider": "google"})
    code_verifier = secrets.token_urlsafe(64)

    request.session.clear()
    request.session["google_oauth_state"] = signed_state
    request.session["google_oauth_code_verifier"] = code_verifier

    authorization_url, _ = create_authorization_url(
        state=signed_state,
        code_verifier=code_verifier,
    )
    return RedirectResponse(url=authorization_url, status_code=302)


@router.get("/callback", response_class=HTMLResponse)
async def google_auth_callback(
    request: Request,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    try:
        if error:
            raise HTTPException(status_code=400, detail=f"Google OAuth error: {error}")

        if not code or not state:
            raise HTTPException(status_code=400, detail="Missing code or state.")

        expected_state = request.session.get("google_oauth_state")
        if not expected_state:
            raise HTTPException(status_code=400, detail="Missing OAuth state in session.")

        if state != expected_state:
            raise HTTPException(status_code=400, detail="OAuth state mismatch.")

        try:
            state_signer.loads(state)
        except BadSignature as exc:
            raise HTTPException(status_code=400, detail="Invalid OAuth state.") from exc

        code_verifier = request.session.get("google_oauth_code_verifier")
        if not code_verifier:
            raise HTTPException(status_code=400, detail="Missing PKCE code verifier in session.")

        token_data = fetch_tokens_from_callback(
            code=code,
            state=state,
            code_verifier=code_verifier,
        )
        userinfo = fetch_google_userinfo(access_token=token_data["token"])

        email = userinfo.get("email")
        full_name = userinfo.get("name")

        if not email:
            raise HTTPException(status_code=400, detail="Google account email not returned.")

        user = db.query(User).filter(User.email == email).first()
        if user is None:
            user = User(email=email, full_name=full_name)
            db.add(user)
            db.flush()
        else:
            user.full_name = full_name

        expiry = None
        if token_data.get("expiry"):
            expiry = datetime.fromisoformat(token_data["expiry"])

        google_account = db.query(GoogleAccount).filter(GoogleAccount.google_email == email).first()
        if google_account is None:
            google_account = GoogleAccount(
                user_id=user.id,
                google_email=email,
                access_token=token_data["token"],
                refresh_token=token_data.get("refresh_token"),
                token_uri=token_data.get("token_uri"),
                scopes=" ".join(token_data.get("scopes", [])),
                expiry=expiry,
            )
            db.add(google_account)
        else:
            google_account.user_id = user.id
            google_account.access_token = token_data["token"]
            google_account.refresh_token = token_data.get("refresh_token") or google_account.refresh_token
            google_account.token_uri = token_data.get("token_uri")
            google_account.scopes = " ".join(token_data.get("scopes", []))
            google_account.expiry = expiry

        db.commit()

        request.session.clear()

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
              <p><strong>Email:</strong> {email}</p>
              <p><strong>Name:</strong> {full_name or "unknown"}</p>
              <p><strong>Saved to database:</strong> yes</p>
              <p><strong>Refresh token received:</strong> {"yes" if token_data.get("refresh_token") else "no"}</p>
              <p><strong>Scopes granted:</strong></p>
              <ul>
                {''.join(f"<li><code>{scope}</code></li>" for scope in token_data.get("scopes", []))}
              </ul>
              <p><a href="/inbox">Go to inbox</a></p>
            </div>
          </body>
        </html>
        """
        return HTMLResponse(content=html)

    except HTTPException as exc:
        return HTMLResponse(
            content=f"""
            <html>
              <body style="font-family: Arial; max-width: 900px; margin: 40px auto;">
                <h1>OAuth callback failed</h1>
                <p><strong>Error:</strong> {exc.detail}</p>
              </body>
            </html>
            """,
            status_code=exc.status_code,
        )
    except Exception as exc:
        db.rollback()
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
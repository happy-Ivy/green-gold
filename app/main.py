from datetime import datetime
from pathlib import Path
import os
from io import BytesIO

from fastapi import FastAPI, Request, Form, Depends, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware
from sqlmodel import Session, select
from openpyxl import Workbook
from dotenv import load_dotenv

from .db import init_db, get_session
from .models import User, TransactionCode, PointLog
from .security import gen_code

load_dotenv()

# =========================
# App 基本設定
# =========================

app = FastAPI(title="Green Points")
app.add_middleware(SessionMiddleware, secret_key="CHANGE_ME_TO_A_LONG_RANDOM_SECRET")

BASE_DIR = Path(__file__).resolve().parent
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


# =========================
# 工具函數
# =========================

def admin_whitelist() -> set[str]:
    raw = os.getenv("ADMIN_EMAILS", "")
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def require_login(request: Request) -> dict:
    user_id = request.session.get("user_id")
    role = request.session.get("role")
    if not user_id or not role:
        raise HTTPException(status_code=401, detail="Not logged in")
    return {"user_id": user_id, "role": role}


@app.on_event("startup")
def on_startup():
    init_db()


# =========================
# 首頁
# =========================

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})
@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    return templates.TemplateResponse("login.html", {"request": request})

# =========================
# 🔐 直接登入（無 OTP）
# =========================

@app.post("/login")
def login(
    request: Request,
    email: str = Form(...),
    role: str = Form(...),
    session: Session = Depends(get_session)
):
    email = email.strip().lower()

    if role not in ("user", "merchant", "admin"):
        raise HTTPException(400, "Invalid role")

    # admin 必須白名單
    if role == "admin" and email not in admin_whitelist():
        raise HTTPException(403, "Admin not allowed")

    user = session.exec(select(User).where(User.email == email)).first()

    if not user:
        if role == "admin":
            raise HTTPException(403, "Admin must be pre-approved")
        user = User(email=email, role=role)
        session.add(user)
        session.commit()
        session.refresh(user)
    else:
        role = user.role

    request.session["user_id"] = user.id
    request.session["role"] = user.role

    return RedirectResponse("/home", status_code=303)


@app.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)


# =========================
# 規則頁
# =========================

@app.get("/rules", response_class=HTMLResponse)
def rules_page(request: Request):
    require_login(request)
    return templates.TemplateResponse("rules.html", {"request": request})


# =========================
# Dashboard
# =========================

@app.get("/home", response_class=HTMLResponse)
def home(request: Request, session: Session = Depends(get_session)):
    auth = require_login(request)
    user = session.get(User, auth["user_id"])

    if not user:
        request.session.clear()
        return RedirectResponse("/", status_code=303)

    # Admin
    if user.role == "admin":
        users = session.exec(select(User).order_by(User.id.desc())).all()
        codes = session.exec(select(TransactionCode).order_by(TransactionCode.id.desc())).all()
        logs = session.exec(select(PointLog).order_by(PointLog.id.desc())).all()
        return templates.TemplateResponse(
            "admin_home.html",
            {"request": request, "user": user, "users": users, "codes": codes, "logs": logs},
        )

    # Merchant
    if user.role == "merchant":
        codes = session.exec(
            select(TransactionCode)
            .where(TransactionCode.merchant_id == user.id)
            .order_by(TransactionCode.id.desc())
        ).all()
        return templates.TemplateResponse(
            "merchant_home.html",
            {"request": request, "user": user, "codes": codes},
        )

    # User
    logs = session.exec(
        select(PointLog)
        .where(PointLog.user_id == user.id)
        .order_by(PointLog.id.desc())
    ).all()
    return templates.TemplateResponse(
        "user_home.html",
        {"request": request, "user": user, "logs": logs},
    )


# =========================
# Admin 匯出
# =========================

@app.get("/admin/export")
def admin_export(request: Request, session: Session = Depends(get_session)):
    auth = require_login(request)
    user = session.get(User, auth["user_id"])
    if user.role != "admin":
        raise HTTPException(403)

    wb = Workbook()

    ws = wb.active
    ws.title = "users"
    ws.append(["id", "email", "role", "green_points", "created_at"])

    users = session.exec(select(User)).all()
    for u in users:
        ws.append([u.id, u.email, u.role, u.green_points, str(u.created_at)])

    bio = BytesIO()
    wb.save(bio)
    bio.seek(0)

    filename = f"green_points_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.xlsx"

    return StreamingResponse(
        bio,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


# =========================
# Merchant 建立代碼
# =========================

@app.post("/merchant/create")
def merchant_create_code(
    request: Request,
    points: int = Form(...),
    session: Session = Depends(get_session),
):
    auth = require_login(request)
    if auth["role"] != "merchant":
        raise HTTPException(403)

    code = gen_code(8)
    rec = TransactionCode(code=code, merchant_id=auth["user_id"], points=points)

    session.add(rec)
    session.commit()

    return RedirectResponse("/home", status_code=303)


# =========================
# 使用者兌換
# =========================

@app.post("/redeem")
def redeem(
    request: Request,
    code: str = Form(...),
    session: Session = Depends(get_session),
):
    auth = require_login(request)
    if auth["role"] != "user":
        raise HTTPException(403)

    rec = session.exec(
        select(TransactionCode).where(TransactionCode.code == code.strip().upper())
    ).first()

    if not rec or rec.is_used:
        raise HTTPException(400, "Invalid code")

    user = session.get(User, auth["user_id"])

    user.green_points += rec.points
    rec.is_used = True
    rec.used_at = datetime.utcnow()
    rec.used_by_user_id = user.id

    log = PointLog(
        user_id=user.id,
        merchant_id=rec.merchant_id,
        points=rec.points,
        code=rec.code
    )

    session.add(user)
    session.add(rec)
    session.add(log)
    session.commit()

    return RedirectResponse("/home", status_code=303)
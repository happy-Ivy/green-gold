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
from .security import gen_tx_code_6

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
        user = User(email=email, role=role)
        session.add(user)
        session.commit()
        session.refresh(user)
    else:
        # ⭐ 核心修正
        if role == "admin" and email in admin_whitelist():
            user.role = "admin"
        else:
            user.role = role

        session.add(user)
        session.commit()

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
    # 不用登入也可以看遊戲規則
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
# Merchant 建立代碼（兩段式）
# =========================

@app.get("/merchant/create", response_class=HTMLResponse)
def merchant_create_page(request: Request):
    auth = require_login(request)
    if auth["role"] != "merchant":
        raise HTTPException(403)

    return templates.TemplateResponse("merchant_create.html", {"request": request})

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

    if points < 0 or points > 999:
        raise HTTPException(status_code=400, detail="points must be 0~999")

    # ✅ 6 碼：前三碼英文隨機 + 後三碼點數（003）
    code = gen_tx_code_6(points)

    # 保險：避免極低機率重複（unique=True 會擋，但這裡先預防）
    # 若撞碼就再產生一次（通常不會發生）
    existing = session.exec(select(TransactionCode).where(TransactionCode.code == code)).first()
    if existing:
        code = gen_tx_code_6(points)

    rec = TransactionCode(code=code, merchant_id=auth["user_id"], points=points)

    session.add(rec)
    session.commit()

    return RedirectResponse("/home", status_code=303)
# =========================
# 使用者輸入交易代碼頁（GET）
# =========================

@app.get("/redeem", response_class=HTMLResponse)
def redeem_page(request: Request):
    auth = require_login(request)
    if auth["role"] != "user":
        raise HTTPException(403)
    return templates.TemplateResponse("redeem.html", {"request": request})

# =========================
# 使用者兌換
# =========================

@app.post("/redeem", response_class=HTMLResponse)
def redeem(
    request: Request,
    code: str = Form(...),
    session: Session = Depends(get_session),
):
    auth = require_login(request)
    if auth["role"] != "user":
        raise HTTPException(403)

    code_norm = code.strip().upper()

    rec = session.exec(
        select(TransactionCode).where(TransactionCode.code == code_norm)
    ).first()

    if not rec:
        return templates.TemplateResponse(
            "redeem.html",
            {"request": request, "error": "交易代碼不存在，請確認後再輸入。"},
            status_code=400
        )

    if rec.is_used:
        return templates.TemplateResponse(
            "redeem.html",
            {"request": request, "error": "此交易代碼已兌換過，無法重複使用。"},
            status_code=400
        )

    user = session.get(User, auth["user_id"])
    if not user:
        request.session.clear()
        return RedirectResponse("/", status_code=303)

    # 發放點數
    user.green_points += rec.points

    # 標記已使用
    rec.is_used = True
    rec.used_at = datetime.utcnow()
    rec.used_by_user_id = user.id

    # 紀錄
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
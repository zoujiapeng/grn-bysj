from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from ..database import get_db
from ..deps import get_current_user
from ..models import User
from ..schemas import LoginRequest, PasswordChangeRequest, RegisterRequest, TokenOut, UserOut
from ..security import create_access_token, hash_password, verify_password


router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/register", response_model=TokenOut, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    username = payload.username.strip()
    email = payload.email.lower().strip()
    exists = db.scalar(select(User).where(or_(User.username == username, User.email == email)))
    if exists:
        raise HTTPException(status_code=409, detail="用户名或邮箱已存在")
    is_first = (db.scalar(select(func.count(User.id))) or 0) == 0
    user = User(
        username=username,
        email=email,
        password_hash=hash_password(payload.password),
        is_admin=is_first,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return TokenOut(access_token=create_access_token(user.id), user=UserOut.model_validate(user))


@router.post("/login", response_model=TokenOut)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    identifier = payload.username.strip()
    user = db.scalar(select(User).where(or_(User.username == identifier, User.email == identifier.lower())))
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="账号已停用")
    return TokenOut(access_token=create_access_token(user.id), user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)):
    return user


@router.put("/password")
def change_password(
    payload: PasswordChangeRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(payload.old_password, user.password_hash):
        raise HTTPException(status_code=400, detail="原密码不正确")
    user.password_hash = hash_password(payload.new_password)
    db.commit()
    return {"message": "密码修改成功"}

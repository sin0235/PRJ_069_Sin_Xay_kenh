"""Lưu thông tin xác thực mật khẩu cục bộ trong kho Baha Auth."""

from sqlalchemy.orm import Session

from baha_auth.src.models.entities import LocalPasswordCredential


def get_password_hash(db: Session, user_id: str) -> str | None:
    credential = db.get(LocalPasswordCredential, user_id)
    return credential.password_hash if credential else None


def create_password_credential_if_missing(db: Session, user_id: str, password_hash: str) -> bool:
    if db.get(LocalPasswordCredential, user_id) is not None:
        return False
    db.add(LocalPasswordCredential(user_id=user_id, password_hash=password_hash))
    db.flush()
    return True

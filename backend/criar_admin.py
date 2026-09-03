"""Cria ou redefine um administrador do Batalha Farejador.

Execute na pasta backend (o banco usado é o mesmo do servidor):
    python criar_admin.py
"""
import getpass
import sys
from sqlalchemy import select

from app.db.session import SessionLocal, Base, engine
from app.models import User
from app.core.security import hash_password

def main():
    Base.metadata.create_all(bind=engine)
    db=SessionLocal()
    try:
        email=input("E-mail do administrador: ").strip().lower()
        if not email:
            raise SystemExit("E-mail obrigatório.")
        username=input("Nome de usuário [admin]: ").strip() or "admin"
        password=getpass.getpass("Nova senha: ")
        confirm=getpass.getpass("Confirme a senha: ")
        if len(password)<8:
            raise SystemExit("A senha precisa ter pelo menos 8 caracteres.")
        if password!=confirm:
            raise SystemExit("As senhas não conferem.")

        user=db.scalar(select(User).where(User.email==email))
        if user:
            user.username=username
            user.password_hash=hash_password(password)
            user.role="admin"
            user.is_active=True
        else:
            user=User(email=email,username=username,password_hash=hash_password(password),
                      role="admin",is_active=True)
            db.add(user)
        db.commit()
        print(f"\nAdministrador pronto: {user.email}")
        print("Acesse o painel administrativo em http://127.0.0.1:5174")
    finally:
        db.close()

if __name__=="__main__":
    main()

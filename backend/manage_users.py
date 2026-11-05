"""Administrare utilizatori din linia de comandă (rulează din folderul backend/, cu venv activ).

  python manage_users.py list
  python manage_users.py create <utilizator> [--admin] [--nume "Ion Popescu"]
  python manage_users.py set-password <utilizator>
  python manage_users.py disable <utilizator>
  python manage_users.py enable <utilizator>
"""
import argparse
import getpass
import sys

import models
from database import SessionLocal
from migrations import ruleaza_migrari
from security import hash_password


def _parola() -> str:
    while True:
        p1 = getpass.getpass("Parolă nouă (min. 8 caractere): ")
        if len(p1) < 8:
            print("Prea scurtă.")
            continue
        if p1 != getpass.getpass("Repetă parola: "):
            print("Parolele nu coincid.")
            continue
        return p1


def main() -> int:
    ap = argparse.ArgumentParser(description="Utilizatori Silmar Agri ERP")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    c = sub.add_parser("create")
    c.add_argument("username")
    c.add_argument("--admin", action="store_true")
    c.add_argument("--nume", default=None)
    for nume in ("set-password", "disable", "enable"):
        sub.add_parser(nume).add_argument("username")
    args = ap.parse_args()

    ruleaza_migrari()
    with SessionLocal() as db:
        if args.cmd == "list":
            for u in db.query(models.User).order_by(models.User.id):
                print(f"{u.id:>3}  {u.username:<20} {'admin' if u.is_admin else 'user':<6} "
                      f"{'activ' if u.is_active else 'DEZACTIVAT':<11} ultima logare: {u.last_login or '-'}")
            return 0

        user = db.query(models.User).filter(models.User.username == args.username).first()
        if args.cmd == "create":
            if user:
                print("Utilizatorul există deja.")
                return 1
            db.add(models.User(username=args.username, nume=args.nume, is_admin=args.admin,
                               password_hash=hash_password(_parola())))
        elif not user:
            print("Utilizatorul nu există.")
            return 1
        elif args.cmd == "set-password":
            user.password_hash = hash_password(_parola())
        elif args.cmd in ("disable", "enable"):
            user.is_active = args.cmd == "enable"
        db.commit()
        print("Gata.")
    return 0


if __name__ == "__main__":
    sys.exit(main())

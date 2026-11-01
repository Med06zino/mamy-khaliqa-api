#!/usr/bin/env python
"""Script pour creer un superuser"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.accounts.models import User

email = "mn9792783@gmail.com"
password = "Medzino06@"

try:
    user = User.objects.get(email=email)
    user.is_staff = True
    user.is_superuser = True
    user.set_password(password)
    user.save()
    print(f"Superuser mis a jour: {email}")
except User.DoesNotExist:
    user = User.objects.create_superuser(
        email=email,
        password=password,
        first_name="Mederic",
        last_name="Diagne",
        phone="221770000000",
    )
    print(f"Superuser cree: {email}")

print(f"Mot de passe: {password}")
print("Vous pouvez maintenant vous connecter !")

#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.accounts.models import User

email = "mamy@khaliqa.com"
password = "mamykhaliqa"

try:
    user = User.objects.get(email=email)
    user.is_superuser = True
    user.is_staff = True
    user.set_password(password)
    user.save()
    print(f"Superuser mise a jour: {email}")
except User.DoesNotExist:
    user = User.objects.create_superuser(
        email=email,
        password=password,
        first_name="Mamy",
        last_name="Khaliqa",
        phone="221770000000",
    )
    print(f"Superuser cree: {email}")

print(f"Mot de passe: {password}")
print("Vous pouvez maintenant vous connecter !")

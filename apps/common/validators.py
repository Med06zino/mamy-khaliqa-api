from django.conf import settings
from django.core.exceptions import ValidationError

ALLOWED_IMAGE_FORMATS = {"JPEG", "PNG", "WEBP"}


def validate_image(file):
    """Controle taille et format reel (Pillow) des images televersees."""
    from PIL import Image

    if file.size > settings.MAX_IMAGE_UPLOAD_BYTES:
        raise ValidationError("L'image depasse la taille maximale de 5 Mo.")
    try:
        img = Image.open(file)
        fmt = img.format
        img.verify()
    except Exception:
        raise ValidationError("Le fichier n'est pas une image valide.")
    finally:
        file.seek(0)
    if fmt not in ALLOWED_IMAGE_FORMATS:
        raise ValidationError("Formats acceptes : JPEG, PNG, WEBP.")

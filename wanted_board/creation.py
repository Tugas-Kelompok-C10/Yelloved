import uuid

from django.core import signing
from django.core.exceptions import ValidationError


TOKEN_SALT = "wanted_board.create"


def issue_creation_token(user):
    return signing.dumps(
        {"uid": str(uuid.uuid4()), "user_id": user.pk}, salt=TOKEN_SALT
    )


def creation_uid(token, user):
    try:
        data = signing.loads(token, salt=TOKEN_SALT)
        if data["user_id"] != user.pk:
            raise ValueError("Different user")
        return uuid.UUID(data["uid"])
    except (signing.BadSignature, KeyError, TypeError, ValueError) as error:
        raise ValidationError(
            "This create form is no longer valid. Please reopen the Wanted Board to try again."
        ) from error

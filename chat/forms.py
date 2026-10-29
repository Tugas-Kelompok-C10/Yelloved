from django import forms


class MessageForm(forms.Form):
    body = forms.CharField(max_length=1000, strip=True)
    client_id = forms.UUIDField()


class MessageEditForm(forms.Form):
    body = forms.CharField(max_length=1000, strip=True)
    revision = forms.DateTimeField()

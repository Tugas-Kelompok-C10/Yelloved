from django import template
from chat.session import chat_identity

register = template.Library()


@register.simple_tag(takes_context=True)
def chat_session_identity(context):
    return chat_identity(context["request"])

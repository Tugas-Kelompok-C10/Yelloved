"""Definition of the four dashboard tabs, shared by the page and the navbar popover."""

# request = someone asks for an item. offer = someone offers an item for a wanted post
TABS = [
    {
        'key': 'incoming', 'label': 'Incoming Requests', 'actionable': True,
        'short': 'People asking for your items',
        'description': 'People who asked for your items. Accept a request to mark the item as unavailable '
                       'and reveal the requester\'s contact, or reject it if it is not a good fit. '
                       'Once a request is accepted, other requests for the same item are rejected automatically.',
        'empty': 'Requests from other people for your items will appear here.',
    },
    {
        'key': 'sent', 'label': 'Sent Requests', 'actionable': False,
        'short': 'Items you asked for',
        'description': 'Items owned by other people that you requested. Track their status here, cancel '
                       'while a request is still pending, and see the owner\'s contact once it is accepted.',
        'empty': 'Requests you send to item owners will appear here.',
    },
    {
        'key': 'offers_received', 'label': 'Incoming Offers', 'actionable': True,
        'short': 'Items offered for your wanted posts',
        'description': 'Items other people offered for your wanted posts. Accept the best match and your '
                       'wanted post is marked as fulfilled automatically, while the '
                       'other offers are rejected.',
        'empty': 'Item offers for your wanted posts will appear here.',
    },
    {
        'key': 'offers_sent', 'label': 'Sent Offers', 'actionable': False,
        'short': 'Your items offered to wanted posts',
        'description': 'Your items that you offered to other people\'s wanted posts. Withdraw an offer '
                       'while it is still pending, and see the wanted post owner\'s contact once it is accepted.',
        'empty': 'Items you offer to other people\'s wanted posts will appear here.',
    },
]
TAB_KEYS = tuple(t['key'] for t in TABS)

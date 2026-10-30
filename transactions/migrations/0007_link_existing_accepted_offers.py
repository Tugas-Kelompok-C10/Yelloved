from django.db import migrations


def link_existing(apps, schema_editor):
    Offer = apps.get_model('item_matching', 'ItemOffer')
    Order = apps.get_model('transactions', 'Transaction')
    Post = apps.get_model('wanted_board', 'WantedPost')
    Receipt = apps.get_model('transactions', 'TransactionItem')
    db = schema_editor.connection.alias
    for offer in Offer.objects.using(db).filter(status='accepted').select_related('item', 'wanted_post').iterator():
        if Order.objects.using(db).filter(accepted_offer_id=offer.pk).exists():
            continue
        price = offer.offered_price if offer.offered_price is not None else (offer.item.price if offer.item_id else None)
        # Old accepted free/trade listings can have no price; preserve them as COD Rp0.
        order = Order.objects.using(db).create(
            order_id=f'WANTED-{offer.pk}', accepted_offer_id=offer.pk,
            buyer_id=offer.wanted_post.requester_id, seller_id=offer.offerer_id,
            item_name=offer.item.title if offer.item_id else offer.wanted_post.title,
            total_amount=price or 0, shipping_address=offer.wanted_post.location,
            payment_method='cod',
        )
        if offer.item_id:
            Receipt.objects.using(db).create(transaction_id=order.pk, item_id=offer.item_id, seller_id=offer.offerer_id)
        Post.objects.using(db).filter(pk=offer.wanted_post_id, status__in=['open', 'fulfilled']).update(status='matched')


class Migration(migrations.Migration):
    dependencies = [('transactions', '0006_transaction_accepted_offer_transaction_seller'),
                    ('wanted_board', '0019_alter_wantedpost_status')]
    operations = [migrations.RunPython(link_existing, migrations.RunPython.noop)]

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import Q, Exists, OuterRef, Value, BooleanField
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_http_methods, require_GET, require_POST

from .forms import ItemFilterForm, ItemForm
from .models import Item


def catalog(request):
    form = ItemFilterForm(request.GET)
    queryset = with_favorites(Item.objects.all(), request.user)
    if form.is_valid():
        data = form.cleaned_data
        if data['q']:
            queryset = queryset.filter(Q(title__icontains=data['q']) | Q(description__icontains=data['q']))
        for key in ('category', 'condition', 'listing_type', 'status'):
            if data[key]:
                queryset = queryset.filter(**{key: data[key]})
    else:
        queryset = queryset.none()
    return form, Paginator(queryset, 12).get_page(request.GET.get('page'))


@require_GET
def explore_items(request):
    form, page = catalog(request)
    return render(request, 'items/explore.html', {'name': 'Yelloved', 'filter_form': form, 'page_obj': page})


@require_GET
def items_json(request):
    form, page = catalog(request)
    if not form.is_valid():
        return JsonResponse({'error': 'Filter tidak valid.', 'errors': form.errors.get_json_data()}, status=400)
    # Explicit public fields only: no owner IDs, email, phone or profile data.
    data = [{'id': item.pk, 'title': item.title, 'description': item.description,
             'category': item.get_category_display(), 'condition': item.get_condition_display(),
             'listing_type': item.get_listing_type_display(), 'price': str(item.price) if item.price is not None else None,
             'currency': item.currency, 'price_display': item.price_display,
             'location': item.location, 'image_url': item.display_image_url,
             'is_favorited': item.is_favorited, 'status': item.get_status_display(), 'detail_url': item.get_absolute_url()} for item in page]
    return JsonResponse({'items': data, 'count': page.paginator.count, 'page': page.number,
                         'pages': page.paginator.num_pages,
                         'html': render_to_string('items/_results.html', {'page_obj': page}, request=request)})


@require_GET
def item_detail(request, item_id):
    item = get_object_or_404(with_favorites(Item.objects.select_related('owner'), request.user), pk=item_id)
    can_manage = request.user.is_authenticated and item.owner_id == request.user.pk and item.source == 'user' and not item.is_catalog
    can_request_item = (request.user.is_authenticated and item.owner_id != request.user.pk and item.owner_id is not None
                        and item.source == 'user' and item.status == Item.Status.AVAILABLE)
    matching_request_form = None
    if can_request_item:
        # Reuse the existing matching contract, including its swap item queryset.
        from item_matching.forms import ItemRequestForm
        matching_request_form = ItemRequestForm(item=item, user=request.user)
    seller_items = (with_favorites(Item.objects.filter(
        owner_id=item.owner_id, status=Item.Status.AVAILABLE,
    ).exclude(pk=item.pk), request.user)[:4] if item.owner_id else Item.objects.none())
    return render(request, 'items/item_detail.html', {
        'name': 'Yelloved', 'item': item, 'can_manage': can_manage,
        'can_request_item': can_request_item, 'matching_request_form': matching_request_form,
        'seller_items': seller_items,
    })


@login_required(login_url='login')
@require_http_methods(['GET', 'POST'])
def item_create(request):
    form = ItemForm(request.POST if request.method == 'POST' else None,
                    request.FILES if request.method == 'POST' else None)
    if request.method == 'POST' and form.is_valid():
        item = form.save(commit=False)
        item.owner = request.user
        item.save()
        messages.success(request, 'Item berhasil ditambahkan.')
        return redirect(item)
    return render(request, 'items/item_form.html', {'name': 'Yelloved', 'form': form, 'editing': False})


def owned_item(request, item_id):
    item = get_object_or_404(Item, pk=item_id)
    if item.owner_id != request.user.pk or item.source != 'user' or item.is_catalog:
        raise PermissionDenied('Hanya pemilik yang dapat mengelola item ini.')
    return item


@login_required(login_url='login')
@require_http_methods(['GET', 'POST'])
def item_update(request, item_id):
    item = owned_item(request, item_id)
    form = ItemForm(request.POST if request.method == 'POST' else None,
                    request.FILES if request.method == 'POST' else None, instance=item)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Item berhasil diperbarui.')
        return redirect(item)
    return render(request, 'items/item_form.html', {'name': 'Yelloved', 'form': form, 'editing': True, 'item': item})


@login_required(login_url='login')
@require_http_methods(['GET', 'POST'])
def item_delete(request, item_id):
    item = owned_item(request, item_id)
    if request.method == 'POST':
        item.delete()
        messages.success(request, 'Item berhasil dihapus.')
        return redirect('items:explore_items')
    return render(request, 'items/item_confirm_delete.html', {'name': 'Yelloved', 'item': item})


def with_favorites(queryset, user):
    if user.is_authenticated:
        liked = Item.liked_by.through.objects.filter(item_id=OuterRef('pk'), user_id=user.pk)
        return queryset.annotate(is_favorited=Exists(liked))
    return queryset.annotate(is_favorited=Value(False, output_field=BooleanField()))


@login_required(login_url='login')
@require_POST
def toggle_favorite(request, item_id):
    item = get_object_or_404(Item, pk=item_id)
    with transaction.atomic():
        # Serialize concurrent toggles by the same user, without changing the item.
        from django.contrib.auth import get_user_model
        get_user_model().objects.select_for_update().get(pk=request.user.pk)
        liked = item.liked_by.filter(pk=request.user.pk).exists()
        if liked:
            item.liked_by.remove(request.user)
        else:
            item.liked_by.add(request.user)
    return JsonResponse({'item_id': item.pk, 'is_favorited': not liked})

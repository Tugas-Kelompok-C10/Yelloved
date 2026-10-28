from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_http_methods, require_GET

from .forms import ItemFilterForm, ItemForm
from .models import Item


def catalog(request):
    form = ItemFilterForm(request.GET)
    queryset = Item.objects.all()
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
             'status': item.get_status_display(), 'detail_url': item.get_absolute_url()} for item in page]
    return JsonResponse({'items': data, 'count': page.paginator.count, 'page': page.number,
                         'pages': page.paginator.num_pages,
                         'html': render_to_string('items/_results.html', {'page_obj': page}, request=request)})


@require_GET
def item_detail(request, item_id):
    item = get_object_or_404(Item.objects.select_related('owner'), pk=item_id)
    can_manage = request.user.is_authenticated and item.owner_id == request.user.pk and item.source == 'user'
    can_request_item = (request.user.is_authenticated and not can_manage and item.owner_id is not None
                        and item.source == 'user' and item.status == Item.Status.AVAILABLE)
    matching_request_form = None
    if can_request_item:
        # Reuse the existing matching contract, including its swap item queryset.
        from item_matching.forms import ItemRequestForm
        matching_request_form = ItemRequestForm(item=item, user=request.user)
    return render(request, 'items/item_detail.html', {
        'name': 'Yelloved', 'item': item, 'can_manage': can_manage,
        'can_request_item': can_request_item, 'matching_request_form': matching_request_form,
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
    if item.owner_id != request.user.pk or item.source != 'user':
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

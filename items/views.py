from django.shortcuts import render


def explore_items(request):
    items = [
        {"name": "Kemeja Linen Cream", "price": "Rp45.000", "condition": "Like New", "location": "Fasilkom UI", "emoji": "👕"},
        {"name": "Lampu Belajar IKEA", "price": "Rp60.000", "condition": "Good", "location": "Kukusan", "emoji": "💡"},
        {"name": "Kalkulator Scientific", "price": "Rp80.000", "condition": "Like New", "location": "Asrama UI", "emoji": "🧮"},
    ]
    query = request.GET.get("q", "").strip()
    condition = request.GET.get("condition", "")
    if condition not in ("Like New", "Good"):
        condition = ""
    if query:
        items = [item for item in items if query.casefold() in f"{item['name']} {item['location']}".casefold()]
    if condition:
        items = [item for item in items if item["condition"] == condition]
    return render(request, "items/explore.html", {
        "name": "Yelloved", "items": items, "query": query, "condition": condition,
    })

"""Pure, deterministic view filtering. Never changes approved template records."""
from __future__ import annotations

def filtered_templates(items, category='Tümü', query='', sort='Kategori / Ad'):
    query=query.strip().casefold()
    visible=[t for t in items if
        (category=='Tümü' or t.get('category')==category) and
        (not query or query in (str(t.get('uid',''))+' '+str(t.get('category',''))+' '+str(t.get('source',''))).casefold())]
    if sort=='Ad (A-Z)':
        return sorted(visible,key=lambda t:(str(t.get('uid','')).casefold(),str(t.get('category',''))))
    if sort=='Ad (Z-A)':
        return sorted(visible,key=lambda t:(str(t.get('uid','')).casefold(),str(t.get('category',''))),reverse=True)
    return sorted(visible,key=lambda t:(str(t.get('category','')),str(t.get('uid','')).casefold()))

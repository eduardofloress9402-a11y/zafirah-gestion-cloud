from sqlalchemy.orm import Session
from .models import Product

CATALOG = [
    ("JAB-AVM", "Avena y Miel", "Jabones"),
    ("JAB-ACM", "Avena, Café y Miel", "Jabones"),
    ("JAB-RRU", "Romero y Ruda", "Jabones"),
    ("JAB-CRS", "Aceite de Coco y Rosas", "Jabones"),
    ("JAB-ARC", "Arcilla Rosa y Coco", "Jabones"),
    ("JAB-MCA", "Manzanilla y Caléndula", "Jabones"),
    ("JAB-CCA", "Coco y Carbón Activado", "Jabones"),
    ("JAB-LAV", "Lavanda", "Jabones"),
    ("JAB-SAN", "Aceite de Coco y Sándalo Hindú", "Jabones"),
    ("JAB-CVA", "Coco y Vainilla", "Jabones"),
    ("JAB-ACI", "Arroz, Aceite de Coco y Cítricos", "Jabones"),
    ("VEL-CAF", "Vela Café", "Velas"),
    ("VEL-EUL", "Vela Eucalipto-Lavanda", "Velas"),
    ("VEL-JAZ", "Vela Jazmín", "Velas"),
    ("VEL-LAV", "Vela Lavanda", "Velas"),
    ("VEL-MYM", "Vela Mango y Maracuyá", "Velas"),
    ("VEL-PAT", "Vela Patchouly", "Velas"),
    ("VEL-RBU", "Vela Rosa Búlgara", "Velas"),
    ("VEL-SDU", "Vela Sándalo Dulce", "Velas"),
    ("VEL-VCO", "Vela Vainilla y Coco", "Velas"),
    ("TAB-ARO", "Tableta aromática", "Tabletas"),
]

def seed_catalog(db: Session):
    existing = {x[0] for x in db.query(Product.sku).all()}
    for sku, name, cat in CATALOG:
        if sku not in existing:
            db.add(Product(sku=sku, name=name, category=cat))
    db.commit()

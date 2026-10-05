from datetime import datetime, date
from decimal import Decimal
from sqlalchemy import String, Integer, DateTime, Date, ForeignKey, Numeric, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .database import Base

D0 = Decimal("0")

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

class Product(Base):
    __tablename__ = "products"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sku: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    category: Mapped[str] = mapped_column(String(80), default="Otros")
    sale_price: Mapped[Decimal] = mapped_column(Numeric(14,2), default=D0)
    cost: Mapped[Decimal] = mapped_column(Numeric(14,4), default=D0)
    stock: Mapped[Decimal] = mapped_column(Numeric(14,3), default=D0)
    min_stock: Mapped[Decimal] = mapped_column(Numeric(14,3), default=D0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)
    recipe: Mapped["Recipe | None"] = relationship(back_populates="product", uselist=False, cascade="all, delete-orphan")

class Material(Base):
    __tablename__ = "materials"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sku: Mapped[str] = mapped_column(String(50), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    unit: Mapped[str] = mapped_column(String(30), default="unidad")
    avg_cost: Mapped[Decimal] = mapped_column(Numeric(14,4), default=D0)
    stock: Mapped[Decimal] = mapped_column(Numeric(14,3), default=D0)
    min_stock: Mapped[Decimal] = mapped_column(Numeric(14,3), default=D0)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

class Recipe(Base):
    __tablename__ = "recipes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), unique=True)
    yield_qty: Mapped[Decimal] = mapped_column(Numeric(14,3), default=Decimal("1"))
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    product: Mapped[Product] = relationship(back_populates="recipe")
    items: Mapped[list["RecipeItem"]] = relationship(cascade="all, delete-orphan", back_populates="recipe")

class RecipeItem(Base):
    __tablename__ = "recipe_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    recipe_id: Mapped[int] = mapped_column(ForeignKey("recipes.id"))
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id"))
    qty: Mapped[Decimal] = mapped_column(Numeric(14,4))
    recipe: Mapped[Recipe] = relationship(back_populates="items")
    material: Mapped[Material] = relationship()

class Supplier(Base):
    __tablename__ = "suppliers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    phone: Mapped[str | None] = mapped_column(String(80), nullable=True)
    email: Mapped[str | None] = mapped_column(String(160), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    phone: Mapped[str | None] = mapped_column(String(80), nullable=True)
    email: Mapped[str | None] = mapped_column(String(160), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

class Purchase(Base):
    __tablename__ = "purchases"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    supplier_id: Mapped[int | None] = mapped_column(ForeignKey("suppliers.id"), nullable=True)
    date: Mapped[date] = mapped_column(Date, default=date.today)
    total: Mapped[Decimal] = mapped_column(Numeric(14,2), default=D0)
    status: Mapped[str] = mapped_column(String(20), default="active")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    supplier: Mapped[Supplier | None] = relationship()
    items: Mapped[list["PurchaseItem"]] = relationship(cascade="all, delete-orphan", back_populates="purchase")

class PurchaseItem(Base):
    __tablename__ = "purchase_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    purchase_id: Mapped[int] = mapped_column(ForeignKey("purchases.id"))
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id"))
    qty: Mapped[Decimal] = mapped_column(Numeric(14,3))
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(14,4))
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14,2))
    purchase: Mapped[Purchase] = relationship(back_populates="items")
    material: Mapped[Material] = relationship()

class Sale(Base):
    __tablename__ = "sales"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    customer_id: Mapped[int | None] = mapped_column(ForeignKey("customers.id"), nullable=True)
    date: Mapped[date] = mapped_column(Date, default=date.today)
    payment_method: Mapped[str] = mapped_column(String(60), default="Efectivo")
    channel: Mapped[str] = mapped_column(String(60), default="Directa")
    total: Mapped[Decimal] = mapped_column(Numeric(14,2), default=D0)
    cogs: Mapped[Decimal] = mapped_column(Numeric(14,2), default=D0)
    profit: Mapped[Decimal] = mapped_column(Numeric(14,2), default=D0)
    status: Mapped[str] = mapped_column(String(20), default="active")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    customer: Mapped[Customer | None] = relationship()
    items: Mapped[list["SaleItem"]] = relationship(cascade="all, delete-orphan", back_populates="sale")

class SaleItem(Base):
    __tablename__ = "sale_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    sale_id: Mapped[int] = mapped_column(ForeignKey("sales.id"))
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    qty: Mapped[Decimal] = mapped_column(Numeric(14,3))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14,2))
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(14,4))
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14,2))
    sale: Mapped[Sale] = relationship(back_populates="items")
    product: Mapped[Product] = relationship()

class ProductionRun(Base):
    __tablename__ = "production_runs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"))
    date: Mapped[date] = mapped_column(Date, default=date.today)
    qty: Mapped[Decimal] = mapped_column(Numeric(14,3))
    total_cost: Mapped[Decimal] = mapped_column(Numeric(14,2), default=D0)
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(14,4), default=D0)
    status: Mapped[str] = mapped_column(String(20), default="active")
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)
    product: Mapped[Product] = relationship()
    items: Mapped[list["ProductionItem"]] = relationship(cascade="all, delete-orphan", back_populates="run")

class ProductionItem(Base):
    __tablename__ = "production_items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    production_id: Mapped[int] = mapped_column(ForeignKey("production_runs.id"))
    material_id: Mapped[int] = mapped_column(ForeignKey("materials.id"))
    qty: Mapped[Decimal] = mapped_column(Numeric(14,4))
    unit_cost: Mapped[Decimal] = mapped_column(Numeric(14,4))
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14,2))
    run: Mapped[ProductionRun] = relationship(back_populates="items")
    material: Mapped[Material] = relationship()

class Expense(Base):
    __tablename__ = "expenses"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    date: Mapped[date] = mapped_column(Date, default=date.today)
    category: Mapped[str] = mapped_column(String(80), default="Otros")
    description: Mapped[str] = mapped_column(String(220))
    amount: Mapped[Decimal] = mapped_column(Numeric(14,2))
    status: Mapped[str] = mapped_column(String(20), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now)

class InventoryMovement(Base):
    __tablename__ = "inventory_movements"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(20))  # product/material
    entity_id: Mapped[int] = mapped_column(Integer)
    entity_name: Mapped[str] = mapped_column(String(160))
    qty_delta: Mapped[Decimal] = mapped_column(Numeric(14,3))
    balance_after: Mapped[Decimal] = mapped_column(Numeric(14,3))
    reason: Mapped[str] = mapped_column(String(220))
    source_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    source_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.now, index=True)

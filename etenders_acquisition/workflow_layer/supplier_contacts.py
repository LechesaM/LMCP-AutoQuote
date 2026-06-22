import sqlite3
from pathlib import Path
from datetime import datetime, timezone

DB_PATH = Path("runtime/workflow/workflow_layer.db")


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def get_conn():
    return sqlite3.connect(DB_PATH)


def upsert_supplier_contact(
    supplier_name,
    contact_person,
    email,
    phone=None,
    branch=None,
    category=None
):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    INSERT INTO supplier_contacts (
        supplier_name,
        contact_person,
        email,
        phone,
        branch,
        category,
        created_at
    )
    VALUES (?, ?, ?, ?, ?, ?, ?)
    ON CONFLICT(supplier_name)
    DO UPDATE SET
        contact_person=excluded.contact_person,
        email=excluded.email,
        phone=excluded.phone,
        branch=excluded.branch,
        category=excluded.category
    """, (
        supplier_name,
        contact_person,
        email,
        phone,
        branch,
        category,
        utc_now()
    ))

    conn.commit()
    conn.close()


def get_supplier_contact(supplier_name):
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    SELECT supplier_name, contact_person, email, phone, branch, category
    FROM supplier_contacts
    WHERE supplier_name = ?
    """, (supplier_name,))

    row = cur.fetchone()
    conn.close()
    return row


def list_suppliers():
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("""
    SELECT supplier_name, contact_person, email, phone, branch, category
    FROM supplier_contacts
    ORDER BY supplier_name
    """)

    rows = cur.fetchall()
    conn.close()
    return rows


if __name__ == "__main__":
    upsert_supplier_contact(
        supplier_name="Builders Warehouse",
        contact_person="Procurement Desk",
        email="quotes@builders.co.za",
        phone="+27-11-000-0000",
        branch="National",
        category="Construction Materials"
    )

    upsert_supplier_contact(
        supplier_name="Bearing Man Group",
        contact_person="Industrial Sales",
        email="sales@bmgworld.net",
        phone="+27-11-000-0001",
        branch="National",
        category="Industrial Supplies"
    )

    for supplier in list_suppliers():
        print(supplier)

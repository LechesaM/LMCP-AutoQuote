from app.db.base import Base
from app.db.models import Tender, TenderDocument, BOQExtraction, BOQItem
from app.db.session import engine


Base.metadata.create_all(engine)

print("Tables created successfully.")

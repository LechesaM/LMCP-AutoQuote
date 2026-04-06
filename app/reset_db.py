from app.database import Base, engine
import app.models  # noqa: F401
from app.models import Opportunity, QuoteDraft


def reset_tables() -> None:
    print("Dropping quote_drafts table if it exists...")
    QuoteDraft.__table__.drop(bind=engine, checkfirst=True)

    print("Dropping opportunities table if it exists...")
    Opportunity.__table__.drop(bind=engine, checkfirst=True)

    print("Creating opportunities table...")
    Opportunity.__table__.create(bind=engine, checkfirst=True)

    print("Creating quote_drafts table...")
    QuoteDraft.__table__.create(bind=engine, checkfirst=True)

    print("Done: tables reset successfully.")


if __name__ == "__main__":
    Base.metadata.create_all(bind=engine)
    reset_tables()

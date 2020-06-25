from peewee import Model, fn
from peewee import BlobField, CharField, ForeignKeyField, IntegerField, PrimaryKeyField, TextField
from playhouse.sqlite_ext import SqliteExtDatabase

# Should likely change where the database files are stored
DATABASE = 'ocr_files.db'

db = SqliteExtDatabase(database=DATABASE, c_extensions=True, pragmas=(
    ('journal_mode', 'wal'),  # Use WAL-mode
    ('foreign_keys', 1),
    ('synchronous', 1)))  # Enforce foreign-key constraints


class BaseModel(Model):
    """Root of database storage hierarchy"""

    class Meta:
        """Metadata for Base Model"""
        database = db


# Table entry for an OCR'ed document
class OcrDocument(BaseModel):
    id = PrimaryKeyField(null=False)
    name = CharField(unique=True)

    # possibly include field for original document extension
    # original = BlobField(null=False)

# Stores an individual page of OCR'ed document
# Also stores the original image file of the page
class OcrPage(BaseModel):
    """Stores all essential information about each page of a document"""
    id = PrimaryKeyField(null=False)
<<<<<<< Updated upstream
    document = ForeignKeyField(OcrDocument, backref='pages')
    number = IntegerField(null=False)  # Page number of doc
    image = BlobField(null=False)
    image_processed = BlobField(null=False)
    ocr_page_data = BlobField(null=False)
=======
    number = IntegerField()  # page number in document
    image = BlobField()  # pipeline-processed image, including cropping out detected texts
    document = ForeignKeyField(OcrDocument, backref='pages')
    ocr_page_data = BlobField(null=False)

# Stores an individual text block with coordinates
class OcrBlock(BaseModel):
    id = PrimaryKeyField(null=False)
    left = IntegerField()
    top = IntegerField()
    width = IntegerField()
    height = IntegerField()
    # Should we store confidence values?
    conf = IntegerField()
    text = TextField()
    page = ForeignKeyField(OcrPage, backref='blocks')
>>>>>>> Stashed changes


# Helper function to intially create the tables in the database
def create_tables():
    with db:
        db.create_tables(models=[OcrDocument, OcrPage])

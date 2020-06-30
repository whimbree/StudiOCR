from peewee import (Model, Check, PrimaryKeyField, CharField,
                    IntegerField, BlobField, ForeignKeyField, TextField)
from playhouse.sqlite_ext import SqliteExtDatabase

# Should likely change where the database files are stored
DATABASE = 'ocr_files.db'

# Do we need c extensions?
db = SqliteExtDatabase(DATABASE, autoconnect=False, c_extensions=False, pragmas={
    'journal_mode': 'delete',  # Use DELETE mode
    'foreign_keys': 1})  # Enforce foreign-key constraints


class BaseModel(Model):
    class Meta:
        database = db


# Table entry for an OCR'ed document
class OcrDocument(BaseModel):
    id = PrimaryKeyField(null=False)
    name = CharField(unique=True)

    def delete_document(self):
        num_rows_deleted = 0
        with db.atomic():
            for page in self.pages:
                for block in page.blocks:
                    block.delete_instance()
                    num_rows_deleted += 1
                page.delete_instance()
                num_rows_deleted += 1
            self.delete_instance()
        return num_rows_deleted + 1


# Stores an individual page of OCR'ed document
# Also stores the original image file of the page
class OcrPage(BaseModel):
    id = PrimaryKeyField(null=False)
    number = IntegerField(null=False and Check('number >= 0'))
    image = BlobField(null=False)
    ocr_page_data = BlobField(null=False)
    document = ForeignKeyField(OcrDocument, backref='pages')


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


# Helper function to intially create the tables in the database
def create_tables():
    with db:
        db.create_tables([OcrDocument, OcrPage, OcrBlock], safe=True)

# Usage
# test = OcrDocument.get(OcrDocument.name == 'test')
# for t in test.pages:
#     for b in t.blocks:
#         print(b.text)

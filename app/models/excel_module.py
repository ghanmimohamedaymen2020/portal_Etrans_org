from datetime import datetime

from app import db


DEFAULT_EXCEL_COLUMNS = [
    ("ref", "REF", "text", True),
    ("date_pic", "DATE PIC", "date", True),
    ("cnne", "CNNE", "text", True),
    ("shipper", "SHIPPER", "text", True),
    ("forwarder", "FORWARDER", "text", True),
    ("offer_ref", "OFFER REF", "text", True),
    ("ro", "R.O.", "text", True),
    ("box", "BOX", "text", True),
    ("cbm", "CBM", "number", True),
    ("teus_value", "TEUS VALUE", "number", True),
    ("tos", "TOS", "text", True),
    ("pol", "POL", "text", True),
    ("org", "ORG", "text", True),
    ("c_readin", "C.READIN", "text", True),
    ("pick_up_c", "PICK UP C", "text", True),
    ("etd", "ETD", "date", True),
    ("via_1", "VIA", "text", True),
    ("ts1_date", "T/S 1 DAT", "date", True),
    ("notifica", "NOTIFICA", "text", True),
    ("pod", "POD", "text", True),
    ("via_2", "VIA 2", "text", True),
    ("carrier", "CARRIER", "text", True),
    ("vessel", "VESSEL", "text", True),
    ("contact_1", "CONTACT", "text", True),
    ("agent", "AGENT", "text", True),
    ("contact_2", "CONTACT 2", "text", True),
    ("commentaire", "COMMENTAIRE", "text", True),
    ("assigne", "ASSIGNE", "text", True),
    ("px_achat", "PX ACHAT", "number", True),
    ("condition", "CONDITION", "text", True),
    ("tchbl", "TCHBL", "text", True),
    ("client_in_contact", "CLIENT IN CONTACT", "text", True),
    ("cgnee", "CGNEE", "text", True),
]


class ExcelColumn(db.Model):
    __tablename__ = "excel_columns"
    __bind_key__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(80), unique=True, nullable=False, index=True)
    label = db.Column(db.String(120), nullable=False)
    data_type = db.Column(db.String(20), nullable=False, default="text")
    is_default = db.Column(db.Boolean, nullable=False, default=False)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    position = db.Column(db.Integer, nullable=False, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.String(80))


class ExcelRecord(db.Model):
    __tablename__ = "excel_records"
    __bind_key__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    ref = db.Column(db.String(120), index=True)
    date_pic = db.Column(db.Date)
    cnne = db.Column(db.String(255))
    shipper = db.Column(db.String(255))
    forwarder = db.Column(db.String(255))
    offer_ref = db.Column(db.String(255))
    ro = db.Column(db.String(120))
    box = db.Column(db.String(120))
    cbm = db.Column(db.Float)
    teus_value = db.Column(db.Float)
    tos = db.Column(db.String(120))
    pol = db.Column(db.String(120))
    org = db.Column(db.String(120))
    c_readin = db.Column(db.String(120))
    pick_up_c = db.Column(db.String(120))
    etd = db.Column(db.Date)
    via_1 = db.Column(db.String(120))
    ts1_date = db.Column(db.Date)
    notifica = db.Column(db.String(255))
    pod = db.Column(db.String(120))
    via_2 = db.Column(db.String(120))
    carrier = db.Column(db.String(120))
    vessel = db.Column(db.String(120))
    contact_1 = db.Column(db.String(255))
    agent = db.Column(db.String(120))
    contact_2 = db.Column(db.String(255))
    commentaire = db.Column(db.Text)
    assigne = db.Column(db.String(120))
    px_achat = db.Column(db.Float)
    condition = db.Column(db.String(120))
    tchbl = db.Column(db.String(120))
    client_in_contact = db.Column(db.String(255))
    cgnee = db.Column(db.String(255))

    created_by = db.Column(db.String(80))
    updated_by = db.Column(db.String(80))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ExcelRecordExtraValue(db.Model):
    __tablename__ = "excel_record_extra_values"
    __bind_key__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    record_id = db.Column(db.Integer, db.ForeignKey("excel_records.id", ondelete="CASCADE"), nullable=False, index=True)
    column_id = db.Column(db.Integer, db.ForeignKey("excel_columns.id", ondelete="CASCADE"), nullable=False, index=True)
    value = db.Column(db.Text)

    record = db.relationship(
        "ExcelRecord",
        backref=db.backref("extra_values", cascade="all, delete-orphan", lazy="joined"),
    )
    column = db.relationship("ExcelColumn", lazy="joined")

    __table_args__ = (
        db.UniqueConstraint("record_id", "column_id", name="uq_excel_record_col"),
    )

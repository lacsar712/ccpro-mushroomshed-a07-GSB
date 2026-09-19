from marshmallow import Schema, fields, validate

GRADES = ("A", "B", "C")


class HarvestQuotaDayCreateSchema(Schema):
    room_id = fields.Int(required=True, data_key="roomId")
    work_date = fields.Date(required=True, data_key="workDate")
    grade = fields.Str(required=True, validate=validate.OneOf(GRADES))
    cap_kg = fields.Float(
        required=True,
        data_key="capKg",
        validate=validate.Range(min=0.0001, error="capKg 须大于 0"),
    )


class HarvestQuotaDayOutSchema(Schema):
    id = fields.Int(dump_only=True)
    room_id = fields.Int(data_key="roomId")
    work_date = fields.Date(data_key="workDate")
    grade = fields.Str()
    cap_kg = fields.Float(data_key="capKg")
